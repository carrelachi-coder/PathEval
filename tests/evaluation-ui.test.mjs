import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { describe, it } from "node:test";

const UI_FILES = ["app/layout.jsx", "src/components/evaluation-app.jsx"];

async function readUiSource() {
  const files = await Promise.all(UI_FILES.map((file) => readFile(file, "utf8")));
  return files.join("\n");
}

describe("Vercel evaluation UI", () => {
  it("does not hard-code Chinese interface copy", async () => {
    const source = await readUiSource();

    assert.equal(/[\u3400-\u9fff]/u.test(source), false);
  });

  it("does not render generation model fields", async () => {
    const source = await readFile("src/components/evaluation-app.jsx", "utf8");

    assert.equal(/(?:currentRecord|record)\.model|Model:|Generation model/u.test(source), false);
  });

  it("routes public R2 image URLs through the same-origin image proxy", async () => {
    const source = await readFile("src/components/evaluation-app.jsx", "utf8");

    assert.match(source, /\/image-proxy\?src=/u);
    assert.doesNotMatch(source, /imageMogr2\/thumbnail/u);
  });
});
