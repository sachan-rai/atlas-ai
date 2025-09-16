import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const analyze = async () => {
    if (!file) return;
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("http://localhost:8000/analyze", { method: "POST", body: form });
    const json = await res.json();
    setResult(json);
    setBusy(false);
  };

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1>Atlas AI</h1>
      <p>Upload an image → get AI classification + auto-generated report.</p>

      <input type="file" accept="image/*" onChange={e => setFile(e.target.files?.[0] || null)} />
      <button onClick={analyze} disabled={!file || busy} style={{ marginLeft: 12 }}>
        {busy ? "Analyzing..." : "Analyze"}
      </button>

      {result && (
        <div style={{ marginTop: 24 }}>
          <h3>Result</h3>
          <pre style={{ background: "#111", color: "#0f0", padding: 12, borderRadius: 8 }}>
            {JSON.stringify(result, null, 2)}
          </pre>
          <div dangerouslySetInnerHTML={{ __html: result.report?.markdown?.replace(/\n/g, "<br/>") }} />
        </div>
      )}
    </div>
  );
}
