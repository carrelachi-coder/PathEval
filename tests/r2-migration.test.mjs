import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  getR2ObjectKey,
  replaceImagePath,
  shouldRetryMigrationError,
} from "../scripts/lib/r2-migration.mjs";

describe("getR2ObjectKey", () => {
  it("keeps the model folder and filename from Tencent COS URLs", () => {
    assert.equal(
      getR2ObjectKey(
        "https://pathological-ai-1391583084.cos.ap-beijing.myqcloud.com/gemini/Image_gemini_1.png",
      ),
      "gemini/Image_gemini_1.png",
    );
  });

  it("removes transformation query strings before creating keys", () => {
    assert.equal(
      getR2ObjectKey(
        "https://pathological-ai-1391583084.cos.ap-beijing.myqcloud.com/seedream/image_seedream_3.jpg?imageMogr2/thumbnail/x800",
      ),
      "seedream/image_seedream_3.jpg",
    );
  });
});

describe("replaceImagePath", () => {
  it("joins the public base URL and object key", () => {
    assert.equal(
      replaceImagePath(
        "https://pub-example.r2.dev/",
        "https://pathological-ai-1391583084.cos.ap-beijing.myqcloud.com/qwen/image_qwen_2.png",
      ),
      "https://pub-example.r2.dev/qwen/image_qwen_2.png",
    );
  });
});

describe("shouldRetryMigrationError", () => {
  it("retries transient network failures", () => {
    assert.equal(shouldRetryMigrationError(new Error("fetch failed")), true);
    assert.equal(shouldRetryMigrationError(new Error("read EADDRNOTAVAIL")), true);
    assert.equal(shouldRetryMigrationError(new Error("getaddrinfo ENOTFOUND example.com")), true);
  });

  it("does not retry permanent HTTP download failures", () => {
    assert.equal(shouldRetryMigrationError(new Error("Download failed 404: https://example.com/missing.png")), false);
  });
});
