export function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        i += 1;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }

  const [rawHeaders, ...body] = rows.filter((line) =>
    line.some((value) => value.trim() !== ""),
  );

  if (!rawHeaders) {
    return [];
  }

  const headers = rawHeaders.map((header, index) =>
    index === 0 ? header.replace(/^\uFEFF/, "") : header,
  );

  return body.map((values) => {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = values[index] ?? "";
    });
    return record;
  });
}

export function parseQuestions(value) {
  if (value == null || String(value).trim() === "") {
    return [];
  }

  const text = String(value).trim();
  const jsonReady = text
    .replaceAll("“", '"')
    .replaceAll("”", '"')
    .replaceAll("‘", "'")
    .replaceAll("’", "'");

  try {
    const parsed = JSON.parse(jsonReady);
    if (Array.isArray(parsed)) {
      return parsed
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }
          if (item && typeof item === "object" && "question" in item) {
            return String(item.question);
          }
          return "";
        })
        .map((item) => item.trim())
        .filter(Boolean);
    }
  } catch {
    // Fall through to legacy plain text parsing.
  }

  const normalized = text.replaceAll("？", "?");
  if (normalized.includes("?")) {
    return normalized
      .split("?")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => (part.endsWith("?") ? part : `${part}?`));
  }

  return [text];
}

export function normalizeRecords(rows) {
  return rows
    .filter((row) => row.id && row.image_path)
    .map((row) => ({
      id: String(row.id),
      promptIdx: String(row.prompt_idx ?? ""),
      imagePath: String(row.image_path),
      model: String(row.model ?? ""),
      disease: String(row.disease ?? ""),
      prompt: String(row.prompt ?? ""),
      questions: parseQuestions(row.questions),
    }));
}

function escapeCsvCell(value) {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

export function serializeEvaluationsCsv(evaluations) {
  const headers = [
    "doctor_name",
    "image_id",
    "score_histology",
    "score_cytology",
    "score_microenvironment",
    "comment",
    "checked_features",
    "qa_accuracy",
    "qa_correct_count",
    "qa_total_count",
    "timestamp",
  ];

  const lines = evaluations.map((evaluation) => {
    const checkedFeatures = evaluation.checkedFeatures ?? [];
    const correctCount = checkedFeatures.length;
    const totalCount = Number(evaluation.totalFeatures ?? checkedFeatures.length);
    const accuracy = totalCount > 0 ? correctCount / totalCount : 0;

    return [
      evaluation.doctorName,
      evaluation.imageId,
      evaluation.scoreHistology,
      evaluation.scoreCytology,
      evaluation.scoreMicroenvironment,
      evaluation.comment,
      JSON.stringify(checkedFeatures),
      Number(accuracy.toFixed(4)),
      correctCount,
      totalCount,
      evaluation.timestamp,
    ]
      .map(escapeCsvCell)
      .join(",");
  });

  return `${headers.join(",")}\n${lines.join("\n")}${lines.length ? "\n" : ""}`;
}
