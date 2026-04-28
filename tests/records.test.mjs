import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  parseCsv,
  parseQuestions,
  serializeEvaluationsCsv,
} from "../src/lib/records.mjs";

describe("parseCsv", () => {
  it("parses quoted CSV values that contain commas and escaped quotes", () => {
    const text =
      'id,image_path,prompt,questions\n' +
      '1,https://example.com/a.png,"诊断依据：细胞丰富, 核深染","[""细胞丰富"", ""核深染""]"\n';

    const rows = parseCsv(text);

    assert.deepEqual(rows, [
      {
        id: "1",
        image_path: "https://example.com/a.png",
        prompt: "诊断依据：细胞丰富, 核深染",
        questions: '["细胞丰富", "核深染"]',
      },
    ]);
  });

  it("strips a UTF-8 BOM from the first header", () => {
    const rows = parseCsv("\uFEFFid,image_path\n1,https://example.com/a.png\n");

    assert.deepEqual(rows, [
      {
        id: "1",
        image_path: "https://example.com/a.png",
      },
    ]);
  });
});

describe("parseQuestions", () => {
  it("prefers JSON list strings from data_filtered.csv", () => {
    assert.deepEqual(parseQuestions('["肿瘤呈巢状分布", "间质血管丰富"]'), [
      "肿瘤呈巢状分布",
      "间质血管丰富",
    ]);
  });

  it("falls back to question-mark separated text", () => {
    assert.deepEqual(parseQuestions("是否有坏死？细胞是否异型?"), [
      "是否有坏死?",
      "细胞是否异型?",
    ]);
  });
});

describe("serializeEvaluationsCsv", () => {
  it("serializes comments and checked features safely as CSV", () => {
    const csv = serializeEvaluationsCsv([
      {
        imageId: "1",
        doctorName: "Dr Wang",
        scoreHistology: 4,
        scoreCytology: 3,
        scoreMicroenvironment: 5,
        checkedFeatures: ["细胞丰富", "核深染"],
        comment: 'good, but "soft"',
        timestamp: "2026-04-28T10:00:00.000Z",
      },
    ]);

    assert.equal(
      csv,
      'doctor_name,image_id,score_histology,score_cytology,score_microenvironment,comment,checked_features,qa_accuracy,qa_correct_count,qa_total_count,timestamp\n' +
        'Dr Wang,1,4,3,5,"good, but ""soft""","[""细胞丰富"",""核深染""]",1,2,2,2026-04-28T10:00:00.000Z\n',
    );
  });
});
