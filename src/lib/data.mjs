import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { normalizeRecords, parseCsv } from "./records.mjs";

export async function loadRecords() {
  const preferredPath = path.join(process.cwd(), "data_filtered_r2.csv");
  const dataPath = existsSync(preferredPath)
    ? preferredPath
    : path.join(process.cwd(), "data_filtered.csv");
  const text = await readFile(dataPath, "utf8");
  return normalizeRecords(parseCsv(text));
}
