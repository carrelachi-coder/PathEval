import { existsSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { HeadObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";

import { parseCsv } from "../../src/lib/records.mjs";

export function getR2ObjectKey(imageUrl) {
  const parsed = new URL(imageUrl);
  return decodeURIComponent(parsed.pathname).replace(/^\/+/, "");
}

export function replaceImagePath(publicBaseUrl, imageUrl) {
  const base = publicBaseUrl.replace(/\/+$/, "");
  return `${base}/${getR2ObjectKey(imageUrl)}`;
}

export function shouldRetryMigrationError(error) {
  const message = String(error?.message || error);
  if (/Download failed\s+(400|401|403|404)/.test(message)) {
    return false;
  }
  return /(fetch failed|ENOTFOUND|EAI_AGAIN|EADDRNOTAVAIL|ECONNRESET|ETIMEDOUT|terminated|socket hang up|network)/i.test(
    message,
  );
}

export function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function parseEnvFile(text) {
  const env = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const index = trimmed.indexOf("=");
    if (index === -1) {
      continue;
    }
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

export async function loadR2Config(envFile = ".env.r2") {
  const fromFile = existsSync(envFile)
    ? parseEnvFile(await readFile(envFile, "utf8"))
    : {};
  const source = { ...fromFile, ...process.env };
  const config = {
    accountId: source.R2_ACCOUNT_ID,
    apiToken: source.R2_API_TOKEN,
    accessKeyId: source.R2_ACCESS_KEY_ID,
    secretAccessKey: source.R2_SECRET_ACCESS_KEY,
    endpoint: source.R2_ENDPOINT,
    bucket: source.R2_BUCKET || "patheval-images",
    publicBaseUrl: source.R2_PUBLIC_BASE_URL,
  };

  const missing = Object.entries(config)
    .filter(([key, value]) => key !== "publicBaseUrl" && !value)
    .map(([key]) => key);

  if (missing.length) {
    throw new Error(`Missing R2 config values: ${missing.join(", ")}`);
  }

  return config;
}

export async function cloudflareApi(config, pathname, options = {}) {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${config.accountId}${pathname}`,
    {
      ...options,
      headers: {
        Authorization: `Bearer ${config.apiToken}`,
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    },
  );

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok || data.success === false) {
    const message = data?.errors?.map((error) => error.message).join("; ") || text;
    throw new Error(`Cloudflare API ${response.status}: ${message}`);
  }
  return data.result ?? data;
}

export async function ensureBucket(config) {
  try {
    await cloudflareApi(config, `/r2/buckets/${config.bucket}`);
    return { created: false, bucket: config.bucket };
  } catch (error) {
    if (!String(error.message).includes("404")) {
      throw error;
    }
  }

  await cloudflareApi(config, "/r2/buckets", {
    method: "POST",
    body: JSON.stringify({
      name: config.bucket,
      storage_class: "Standard",
    }),
  });
  return { created: true, bucket: config.bucket };
}

export async function enableManagedDomain(config) {
  const result = await cloudflareApi(
    config,
    `/r2/buckets/${config.bucket}/domains/managed`,
    {
      method: "PUT",
      body: JSON.stringify({ enabled: true }),
    },
  );
  return {
    enabled: Boolean(result.enabled),
    domain: result.domain,
    publicBaseUrl: result.domain ? `https://${result.domain}` : "",
  };
}

export function createR2Client(config) {
  return new S3Client({
    region: "auto",
    endpoint: config.endpoint,
    credentials: {
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.secretAccessKey,
    },
    forcePathStyle: true,
  });
}

export async function objectExistsInR2(client, config, key) {
  try {
    await client.send(
      new HeadObjectCommand({
        Bucket: config.bucket,
        Key: key,
      }),
    );
    return true;
  } catch (error) {
    if (error?.name === "NotFound" || error?.$metadata?.httpStatusCode === 404) {
      return false;
    }
    throw error;
  }
}

export async function uploadImageToR2(client, config, record) {
  const imageUrl = record.image_path;
  const key = getR2ObjectKey(imageUrl);
  const response = await fetch(imageUrl);
  if (!response.ok) {
    throw new Error(`Download failed ${response.status}: ${imageUrl}`);
  }

  const body = new Uint8Array(await response.arrayBuffer());
  const contentType = response.headers.get("content-type") || contentTypeForKey(key);

  await client.send(
    new PutObjectCommand({
      Bucket: config.bucket,
      Key: key,
      Body: body,
      ContentType: contentType,
    }),
  );

  return {
    key,
    bytes: body.byteLength,
    contentType,
    publicUrl: config.publicBaseUrl
      ? `${config.publicBaseUrl.replace(/\/+$/, "")}/${key}`
      : "",
  };
}

export async function uploadImageToR2WithRetry(
  client,
  config,
  record,
  { attempts = 4, baseDelayMs = 750, skipExisting = false } = {},
) {
  const key = getR2ObjectKey(record.image_path);
  if (skipExisting && (await objectExistsInR2(client, config, key))) {
    return {
      key,
      bytes: 0,
      skipped: true,
      publicUrl: config.publicBaseUrl
        ? `${config.publicBaseUrl.replace(/\/+$/, "")}/${key}`
        : "",
    };
  }

  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await uploadImageToR2(client, config, record);
    } catch (error) {
      lastError = error;
      if (attempt === attempts || !shouldRetryMigrationError(error)) {
        throw error;
      }
      await wait(baseDelayMs * attempt);
    }
  }

  throw lastError;
}

export function contentTypeForKey(key) {
  const ext = path.extname(key).toLowerCase();
  if (ext === ".jpg" || ext === ".jpeg") {
    return "image/jpeg";
  }
  if (ext === ".png") {
    return "image/png";
  }
  if (ext === ".webp") {
    return "image/webp";
  }
  return "application/octet-stream";
}

export async function loadSourceRows(csvPath) {
  const text = await readFile(csvPath, "utf8");
  return parseCsv(text);
}

export function rewriteRowsWithR2Urls(rows, publicBaseUrl) {
  return rows.map((row) => ({
    ...row,
    image_path: replaceImagePath(publicBaseUrl, row.image_path),
  }));
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

export function rowsToCsv(rows) {
  if (!rows.length) {
    return "";
  }
  const headers = Object.keys(rows[0]);
  const lines = rows.map((row) => headers.map((key) => csvEscape(row[key])).join(","));
  return `\uFEFF${headers.join(",")}\n${lines.join("\n")}\n`;
}

export async function writeRewrittenCsv(rows, publicBaseUrl, outputPath) {
  const rewritten = rewriteRowsWithR2Urls(rows, publicBaseUrl);
  await writeFile(outputPath, rowsToCsv(rewritten), "utf8");
  return outputPath;
}
