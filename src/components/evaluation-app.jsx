"use client";

import { useEffect, useMemo, useState } from "react";

import { serializeEvaluationsCsv } from "../lib/records.mjs";

const EVALUATIONS_KEY = "patheval:evaluations:v1";
const DOCTOR_KEY = "patheval:doctor:v1";

const defaultDraft = {
  scoreHistology: 3,
  scoreCytology: 3,
  scoreMicroenvironment: 3,
  checkedFeatures: [],
  comment: "",
};

function imageUrlForDisplay(imagePath) {
  if (imagePath.startsWith("http") && !imagePath.includes("?")) {
    return `${imagePath}?imageMogr2/thumbnail/x1000`;
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

export function EvaluationApp({ records }) {
  const [doctorName, setDoctorName] = useState("");
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
        <p>没有读取到评估数据，请确认 data_filtered.csv 已包含 image_path 和 id 列。</p>
      </main>
    );
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
    setLastSaved("已保存到本机浏览器，可随时导出 CSV。");

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
    const safeName = doctorName.trim().replace(/[^\w\u4e00-\u9fa5-]+/g, "_") || "anonymous";
    downloadTextFile(`evaluation_${safeName}_${date}.csv`, csv);
  }

  function clearLocalEvaluations() {
    if (window.confirm("确定清空本机浏览器中的评估记录吗？此操作不会影响其他设备。")) {
      setEvaluations({});
      setDraft(defaultDraft);
      setLastSaved("本机评估记录已清空。");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="brand">PathEval</h1>
          <p className="subtitle">AI 生成病理图像评估</p>
          <label className="field">
            <span>评估者姓名</span>
            <input
              value={doctorName}
              onChange={(event) => setDoctorName(event.target.value)}
              placeholder="请输入姓名"
            />
          </label>
        </div>

        <div className="progress-box">
          <div className="progress-row">
            <span>评估进度</span>
            <strong>
              {evaluatedCount}/{records.length}
            </strong>
          </div>
          <div className="progress-track" aria-hidden="true">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>

        <div className="task-list" aria-label="任务列表">
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
                    {index + 1}. {record.disease || record.id}
                  </span>
                  <span className="task-meta">
                    {record.model} · {record.id}
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
            <h2 className="page-title">{currentRecord.disease || "未命名病种"}</h2>
            <p className="subtitle">
              ID: {currentRecord.id} · Model: {currentRecord.model || "unknown"}
            </p>
          </div>
          <div className="actions">
            <button
              className="button"
              disabled={!currentEvaluationList.length}
              onClick={exportCsv}
              type="button"
            >
              下载 CSV
            </button>
            <button
              className="button"
              disabled={!currentEvaluationList.length}
              onClick={clearLocalEvaluations}
              type="button"
            >
              清空本机记录
            </button>
          </div>
        </div>

        <section className="workspace">
          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">病理图像</h3>
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
                  <div className="info-label">病种</div>
                  <div className="info-value">{currentRecord.disease || "未知"}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">生成模型</div>
                  <div className="info-value">{currentRecord.model || "未知"}</div>
                </div>
              </div>

              <div className="prompt">
                <strong>提示词：</strong>
                {currentRecord.prompt || "无"}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">评分与特征符合度</h3>
            </div>
            <div className="panel-body">
              <div className="score-grid">
                <div className="score-row">
                  <label>
                    组织学结构
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
                    细胞学特征
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
                    微环境表现
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
                  <p className="muted">当前图片没有可勾选特征。</p>
                )}
              </div>

              <label className="field">
                <span>补充备注</span>
                <textarea
                  className="comment-box"
                  onChange={(event) => updateDraft({ comment: event.target.value })}
                  placeholder="可选"
                  value={draft.comment}
                />
              </label>

              <div className="form-footer">
                <span className="status-text">
                  {lastSaved ||
                    (doctorName.trim() ? "填写完成后保存。" : "请先填写评估者姓名。")}
                </span>
                <button
                  className="button primary"
                  disabled={!doctorName.trim()}
                  onClick={() => saveEvaluation(true)}
                  type="button"
                >
                  保存并下一张
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
