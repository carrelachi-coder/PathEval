import { EvaluationApp } from "../src/components/evaluation-app.jsx";
import { loadRecords } from "../src/lib/data.mjs";

export default async function HomePage() {
  const records = await loadRecords();

  return <EvaluationApp records={records} />;
}
