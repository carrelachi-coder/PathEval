"use client";

import { useEffect, useMemo, useState } from "react";

import { serializeEvaluationsCsv } from "../lib/records.mjs";

const EVALUATIONS_KEY = "patheval:evaluations:v1";
const DOCTOR_KEY = "patheval:doctor:v1";
const STARTED_KEY = "patheval:started:v1";
const R2_PUBLIC_BASE_URL = "https://pub-7c46b568179e4640898dada0f351a0f2.r2.dev";

const defaultDraft = {
  scoreHistology: 3,
  scoreCytology: 3,
  scoreMicroenvironment: 3,
  checkedFeatures: [],
  comment: "",
};

const scoringCriteria = {
  histology: {
    title: "Histology structure",
    focus: "Low-power overall architecture and anatomic plausibility.",
    levels: [
      ["1", "Non-biologic structure", "The image is unacceptable and structurally chaotic."],
      ["2", "Wrong organ pattern", "It resembles tissue, but not the target organ or lesion."],
      ["3", "Uncertain structure", "The tissue type is plausible, but the lesion pattern is vague."],
      ["4", "Mostly accurate", "Main structures match the report with reasonable background features."],
      ["5", "Highly accurate", "Clear, layered architecture with typical lesion morphology."],
    ],
  },
  cytology: {
    title: "Cytology features",
    focus: "High-power cellular detail and biologic realism.",
    levels: [
      ["1", "Implausible proportions", "Cell size and nuclear-cytoplasmic relationships are biologically wrong."],
      ["2", "Smearing or artifacts", "Cells are blurred or noise-like with no usable morphology."],
      ["3", "Generic cells", "Cells are plausible but miss the specific features in the report."],
      ["4", "Feature match", "Atypia and key cellular details are visible and report-consistent."],
      ["5", "Excellent detail", "Chromatin texture, nuclear membranes, and cytoplasm are highly realistic."],
    ],
  },
  microenvironment: {
    title: "Microenvironment",
    focus: "Cell arrangement, polarity, stromal response, and tissue interaction.",
    levels: [
      ["1", "Disordered stacking", "Cells are randomly scattered or overlapping without tissue polarity."],
      ["2", "Poor polarity", "The arrangement is incorrect and lacks cohesive organization."],
      ["3", "Isolated tumor", "Tumor cells are present, but stromal or inflammatory interaction is weak."],
      ["4", "Logical interaction", "Cell adhesion and stromal reaction are reasonable."],
      ["5", "Complex ecosystem", "Tumor-stroma interaction is rich and convincing, with supporting cells where appropriate."],
    ],
  },
};

function imageUrlForDisplay(imagePath) {
  try {
    const imageUrl = new URL(imagePath);
    const r2BaseUrl = new URL(R2_PUBLIC_BASE_URL);
    if (imageUrl.origin === r2BaseUrl.origin) {
      return `/image-proxy?src=${encodeURIComponent(imageUrl.toString())}`;
    }
  } catch {
    return imagePath;
  }

  return imagePath;
}

function downloadTextFile(filename, content) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function ScoreHelp({ criteria }) {
  return (
    <span className="score-help">
      <button
        aria-label={`${criteria.title} scoring criteria`}
        className="help-button"
        type="button"
      >
        ?
      </button>
      <span className="score-tooltip" role="tooltip">
        <strong>{criteria.title}</strong>
        <span>{criteria.focus}</span>
        {criteria.levels.map(([score, label, description]) => (
          <span className="criteria-line" key={score}>
            <b>{score} - {label}:</b> {description}
          </span>
        ))}
      </span>
    </span>
  );
}

export function EvaluationApp({ records }) {
  const [doctorName, setDoctorName] = useState("");
  const [hasStarted, setHasStarted] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [evaluations, setEvaluations] = useState({});
  const [draft, setDraft] = useState(defaultDraft);
  const [lastSaved, setLastSaved] = useState("");

  const currentRecord = records[currentIndex];
  const evaluatedCount = Object.keys(evaluations).length;
  const progress = records.length > 0 ? (evaluatedCount / records.length) * 100 : 0;

  useEffect(() => {
    const savedDoctor = window.localStorage.getItem(DOCTOR_KEY);
    const savedEvaluations = window.localStorage.getItem(EVALUATIONS_KEY);

    if (savedDoctor) {
      setDoctorName(savedDoctor);
    }

    if (window.localStorage.getItem(STARTED_KEY) === "true") {
      setHasStarted(true);
    }

    if (savedEvaluations) {
      try {
        setEvaluations(JSON.parse(savedEvaluations));
      } catch {
        setEvaluations({});
      }
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(DOCTOR_KEY, doctorName);
  }, [doctorName]);

  useEffect(() => {
    window.localStorage.setItem(EVALUATIONS_KEY, JSON.stringify(evaluations));
  }, [evaluations]);

  useEffect(() => {
    if (!currentRecord) {
      return;
    }
    setDraft(evaluations[currentRecord.id] ?? defaultDraft);
    setLastSaved("");
  }, [currentRecord, evaluations]);

  const currentEvaluationList = useMemo(() => {
    return Object.values(evaluations).sort((a, b) =>
      String(a.imageId).localeCompare(String(b.imageId), "en", {
        numeric: true,
      }),
    );
  }, [evaluations]);

  if (!records.length) {
    return (
      <main className="empty-state">
        <h1>PathEval</h1>
        <p>No evaluation records were found. Check that data_filtered.csv includes image_path and id columns.</p>
      </main>
    );
  }

  function startEvaluation() {
    if (!doctorName.trim()) {
      return;
    }
    window.localStorage.setItem(STARTED_KEY, "true");
    setHasStarted(true);
  }

  function updateDraft(patch) {
    setDraft((previous) => ({ ...previous, ...patch }));
  }

  function toggleFeature(feature) {
    const selected = new Set(draft.checkedFeatures);
    if (selected.has(feature)) {
      selected.delete(feature);
    } else {
      selected.add(feature);
    }
    updateDraft({ checkedFeatures: Array.from(selected) });
  }

  function saveEvaluation(goNext = true) {
    if (!currentRecord || !doctorName.trim()) {
      return;
    }

    const nextEvaluation = {
      ...draft,
      imageId: currentRecord.id,
      doctorName: doctorName.trim(),
      totalFeatures: currentRecord.questions.length,
      timestamp: new Date().toISOString(),
    };

    setEvaluations((previous) => ({
      ...previous,
      [currentRecord.id]: nextEvaluation,
    }));
    setLastSaved("Saved in this browser. You can export the CSV at any time.");

    if (goNext) {
      const nextUnfinished = records.findIndex(
        (record, index) => index > currentIndex && !evaluations[record.id],
      );
      if (nextUnfinished >= 0) {
        setCurrentIndex(nextUnfinished);
      } else if (currentIndex < records.length - 1) {
        setCurrentIndex(currentIndex + 1);
      }
    }
  }

  function exportCsv() {
    const csv = serializeEvaluationsCsv(currentEvaluationList);
    const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
    const safeName = doctorName.trim().replace(/[^\w-]+/g, "_") || "anonymous";
    downloadTextFile(`evaluation_${safeName}_${date}.csv`, csv);
  }

  function clearLocalEvaluations() {
    if (window.confirm("Clear the evaluation records stored in this browser? This will not affect other devices.")) {
      setEvaluations({});
      setDraft(defaultDraft);
      setLastSaved("Local evaluation records have been cleared.");
    }
  }

  if (!hasStarted) {
    return (
      <main className="welcome-page">
        <section className="welcome-hero">
          <p className="eyebrow">Blind pathology image review</p>
          <h1>PathEval</h1>
          <p>
            Review AI-generated pathology images using structured quality scores and a
            feature checklist. The image generation model is intentionally hidden during
            evaluation.
          </p>

          <label className="field welcome-name">
            <span>Evaluator name</span>
            <input
              autoComplete="name"
              onChange={(event) => setDoctorName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  startEvaluation();
                }
              }}
              placeholder="Enter your name"
              value={doctorName}
            />
          </label>

          <button
            className="button primary start-button"
            disabled={!doctorName.trim()}
            onClick={startEvaluation}
            type="button"
          >
            Start evaluation
          </button>
        </section>

        <section className="welcome-grid" aria-label="Evaluation guide">
          <div className="welcome-panel">
            <h2>Workflow</h2>
            <ol>
              <li>Enter your evaluator name before starting.</li>
              <li>Score each image from 1 to 5 in the three dimensions.</li>
              <li>Hover or focus the question-mark icon beside each score to review the scoring criteria.</li>
              <li>In the checklist, select only features that are truly visible in the pathology image.</li>
              <li>You can revisit completed images from the left task list and update your evaluation.</li>
              <li>Export the CSV after finishing all assigned images.</li>
            </ol>
          </div>

          <div className="welcome-panel">
            <h2>For clinicians</h2>
            <ul>
              <li>This is a blind review. Do not infer or look for the generating model.</li>
              <li>Stay objective and judge only image quality and prompt-feature agreement.</li>
              <li>Checklist selections affect the calculated feature-match accuracy.</li>
              <li>Your work is saved locally in this browser until you export or clear it.</li>
            </ul>
          </div>

          <div className="welcome-panel span-two">
            <h2>Scoring dimensions</h2>
            <div className="dimension-grid">
              <div>
                <h3>Histology</h3>
                <p>Overall low-power architecture and target-organ plausibility.</p>
              </div>
              <div>
                <h3>Cytology</h3>
                <p>High-power cell detail, nuclear features, and biologic realism.</p>
              </div>
              <div>
                <h3>Microenvironment</h3>
                <p>Cell polarity, stromal response, and tumor-tissue interaction.</p>
              </div>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="brand">PathEval</h1>
          <p className="subtitle">Blind pathology image evaluation</p>
          <label className="field">
            <span>Evaluator name</span>
            <input
              value={doctorName}
              onChange={(event) => setDoctorName(event.target.value)}
              placeholder="Enter your name"
            />
          </label>
        </div>

        <div className="progress-box">
          <div className="progress-row">
            <span>Progress</span>
            <strong>
              {evaluatedCount}/{records.length}
            </strong>
          </div>
          <div className="progress-track" aria-hidden="true">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>

        <div className="task-list" aria-label="Task list">
          {records.map((record, index) => {
            const isDone = Boolean(evaluations[record.id]);
            return (
              <button
                className={`task-button ${index === currentIndex ? "active" : ""}`}
                key={record.id}
                onClick={() => setCurrentIndex(index)}
                type="button"
              >
                <span>{isDone ? "✓" : "·"}</span>
                <span>
                  <span className="task-title">
                    Case {index + 1}
                  </span>
                  <span className="task-meta">
                    {isDone ? "Completed" : "Pending"}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <p className="eyebrow">Image {currentIndex + 1}</p>
            <h2 className="page-title">Case {currentIndex + 1}</h2>
            <p className="subtitle">
              Blind review item. AI source details are hidden.
            </p>
          </div>
          <div className="actions">
            <button
              className="button"
              disabled={!currentEvaluationList.length}
              onClick={exportCsv}
              type="button"
            >
              Export CSV
            </button>
            <button
              className="button"
              disabled={!currentEvaluationList.length}
              onClick={clearLocalEvaluations}
              type="button"
            >
              Clear local records
            </button>
          </div>
        </div>

        <section className="workspace">
          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">Pathology image</h3>
            </div>
            <div className="panel-body">
              <div className="image-frame">
                <img
                  alt={`${currentRecord.disease || "Pathology"} image`}
                  className="pathology-image"
                  src={imageUrlForDisplay(currentRecord.imagePath)}
                />
              </div>

              <div className="info-grid">
                <div className="info-item">
                  <div className="info-label">Case diagnosis</div>
                  <div className="info-value">{currentRecord.disease || "Not provided"}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">Review status</div>
                  <div className="info-value">
                    {evaluations[currentRecord.id] ? "Previously evaluated" : "Not yet evaluated"}
                  </div>
                </div>
              </div>

              <div className="prompt">
                <strong>Source prompt: </strong>
                {currentRecord.prompt || "Not provided"}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">Scores and feature match</h3>
            </div>
            <div className="panel-body">
              <p className="guidance">
                Select checklist items only when the feature is actually visible in the
                pathology image.
              </p>
              <div className="score-grid">
                <div className="score-row">
                  <label>
                    <span className="score-label">
                      Histology structure
                      <ScoreHelp criteria={scoringCriteria.histology} />
                    </span>
                    <input
                      max="5"
                      min="1"
                      onChange={(event) =>
                        updateDraft({ scoreHistology: Number(event.target.value) })
                      }
                      type="range"
                      value={draft.scoreHistology}
                    />
                  </label>
                  <div className="score-value">{draft.scoreHistology}</div>
                </div>

                <div className="score-row">
                  <label>
                    <span className="score-label">
                      Cytology features
                      <ScoreHelp criteria={scoringCriteria.cytology} />
                    </span>
                    <input
                      max="5"
                      min="1"
                      onChange={(event) =>
                        updateDraft({ scoreCytology: Number(event.target.value) })
                      }
                      type="range"
                      value={draft.scoreCytology}
                    />
                  </label>
                  <div className="score-value">{draft.scoreCytology}</div>
                </div>

                <div className="score-row">
                  <label>
                    <span className="score-label">
                      Microenvironment
                      <ScoreHelp criteria={scoringCriteria.microenvironment} />
                    </span>
                    <input
                      max="5"
                      min="1"
                      onChange={(event) =>
                        updateDraft({
                          scoreMicroenvironment: Number(event.target.value),
                        })
                      }
                      type="range"
                      value={draft.scoreMicroenvironment}
                    />
                  </label>
                  <div className="score-value">{draft.scoreMicroenvironment}</div>
                </div>
              </div>

              <div className="checklist">
                {currentRecord.questions.length ? (
                  currentRecord.questions.map((feature) => (
                    <label className="check-row" key={feature}>
                      <input
                        checked={draft.checkedFeatures.includes(feature)}
                        onChange={() => toggleFeature(feature)}
                        type="checkbox"
                      />
                      <span>{feature}</span>
                    </label>
                  ))
                ) : (
                  <p className="muted">No checklist features are available for this image.</p>
                )}
              </div>

              <label className="field">
                <span>Optional comments</span>
                <textarea
                  className="comment-box"
                  onChange={(event) => updateDraft({ comment: event.target.value })}
                  placeholder="Add comments about specific image issues"
                  value={draft.comment}
                />
              </label>

              <div className="form-footer">
                <span className="status-text">
                  {lastSaved ||
                    (doctorName.trim() ? "Save when the evaluation is complete." : "Enter an evaluator name first.")}
                </span>
                <button
                  className="button primary"
                  disabled={!doctorName.trim()}
                  onClick={() => saveEvaluation(true)}
                  type="button"
                >
                  Save and next
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
