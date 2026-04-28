#!/usr/bin/env node
import { ensureBucket, enableManagedDomain, loadR2Config } from "./lib/r2-migration.mjs";

const envFile = process.env.R2_ENV_FILE || ".env.r2";
const config = await loadR2Config(envFile);

const bucket = await ensureBucket(config);
console.log(
  bucket.created
    ? `Created R2 bucket: ${bucket.bucket}`
    : `R2 bucket already exists: ${bucket.bucket}`,
);

const domain = await enableManagedDomain(config);
console.log(`r2.dev public access: ${domain.enabled ? "enabled" : "disabled"}`);
console.log(`R2_PUBLIC_BASE_URL=${domain.publicBaseUrl}`);
