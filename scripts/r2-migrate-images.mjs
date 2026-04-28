#!/usr/bin/env node
import {
  createR2Client,
  loadR2Config,
  loadSourceRows,
  uploadImageToR2WithRetry,
  writeRewrittenCsv,
} from "./lib/r2-migration.mjs";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i];
  if (arg.startsWith("--")) {
    args.set(arg.slice(2), process.argv[i + 1] && !process.argv[i + 1].startsWith("--") ? process.argv[++i] : "true");
  }
}

const envFile = args.get("env") || process.env.R2_ENV_FILE || ".env.r2";
const sourceCsv = args.get("source") || "data_filtered.csv";
const outputCsv = args.get("output") || "data_filtered_r2.csv";
const limit = args.has("limit") ? Number(args.get("limit")) : Infinity;
const start = args.has("start") ? Number(args.get("start")) : 1;
const concurrency = Number(args.get("concurrency") || 8);
const attempts = Number(args.get("attempts") || 4);
const skipExisting = args.get("skip-existing") !== "false";

const config = await loadR2Config(envFile);
if (!config.publicBaseUrl) {
  throw new Error("Missing R2_PUBLIC_BASE_URL. Run scripts/r2-setup.mjs first and add the printed value to .env.r2.");
}

const allRows = await loadSourceRows(sourceCsv);
const selectedRows = allRows.slice(start - 1, Number.isFinite(limit) ? start - 1 + limit : undefined);
const client = createR2Client(config);

let completed = 0;
let processed = 0;
let skipped = 0;
let totalBytes = 0;
const failures = [];

async function worker(workerIndex) {
  for (let index = workerIndex; index < selectedRows.length; index += concurrency) {
    const row = selectedRows[index];
    try {
      const result = await uploadImageToR2WithRetry(client, config, row, {
        attempts,
        skipExisting,
      });
      processed += 1;
      if (result.skipped) {
        skipped += 1;
      } else {
        completed += 1;
      }
      totalBytes += result.bytes;
      if (processed % 25 === 0 || processed === selectedRows.length) {
        console.log(
          `processed ${processed}/${selectedRows.length} uploaded=${completed} skipped=${skipped} (${(totalBytes / 1024 / 1024).toFixed(1)} MB new)`,
        );
      }
    } catch (error) {
      processed += 1;
      failures.push({
        id: row.id,
        url: row.image_path,
        error: error.message,
      });
      console.error(`failed ${row.id}: ${error.message}`);
    }
  }
}

await Promise.all(
  Array.from({ length: Math.min(concurrency, selectedRows.length) }, (_, index) =>
    worker(index),
  ),
);

if (failures.length) {
  console.error(`Upload finished with ${failures.length} failures.`);
  process.exitCode = 1;
} else {
  const rowsForCsv = Number.isFinite(limit) || start !== 1 ? selectedRows : allRows;
  const written = await writeRewrittenCsv(rowsForCsv, config.publicBaseUrl, outputCsv);
  console.log(`Uploaded ${completed} images. Skipped existing ${skipped} images.`);
  console.log(`Wrote rewritten CSV: ${written}`);
}
