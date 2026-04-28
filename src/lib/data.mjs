import { readFile } from "node:fs/promises";
import path from "node:path";

import { normalizeRecords, parseCsv } from "./records.mjs";

export async function loadRecords() {
  const dataPath = path.join(process.cwd(), "data_filtered.csv");
  const text = await readFile(dataPath, "utf8");
  return normalizeRecords(parseCsv(text));
}
