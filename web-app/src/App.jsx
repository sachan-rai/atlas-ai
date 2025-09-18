// web-app/src/App.jsx
import { useState, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [file, setFile] = useState(null);
  const [imgUrl, setImgUrl] = useState("");
  const [status, setStatus] = useState("Idle");
  const [result, setResult] = useState(null); // { ml: {...}, report: { markdown } }
  const [error, setError] = useState("");

  // ---- Pick file from input
  const onPick = useCallback((e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setResult(null);
    setError("");
    setImgUrl(URL.createObjectURL(f));
  }, []);

  // ---- Drag & drop (optional)
  const onDrop = useCallback((e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (!f) return;
    setFile(f);
    setResult(null);
    setError("");
    setImgUrl(URL.createObjectURL(f));
  }, []);
  const onDragOver = useCallback((e) => e.preventDefault(), []);

  // ---- Call gateway /upload
  const analyze = useCallback(async () => {
    if (!file) return;
    setStatus("Analyzing...");
    setError("");
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file); // field name must be "file"
      const resp = await fetch(`${API}/upload`, { method: "POST", body: form });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`API ${resp.status}: ${text}`);
      }
      const data = await resp.json(); // { ml: {class, confidence, latency_ms,...}, report: { markdown } }
      setResult(data);
      setStatus("Done");
    } catch (e) {
      console.error(e);
      setStatus("Error");
      setError(e.message || String(e));
    }
  }, [file]);

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      style={{
        minHeight: "100vh",
        background: "#1e1f22",
        color: "#e6e6e6",
        fontFamily:
          "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji",
        padding: "40px 24px",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left column: controls */}
        <div>
          <h1 style={{ fontSize: 64, fontWeight: 800, margin: 0 }}>Atlas AI</h1>
          <p style={{ opacity: 0.85, marginTop: 10 }}>
            Upload an image → get AI classification + auto-generated report.
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 20 }}>
            <label
              style={{
                background: "#2b2d31",
                padding: "8px 12px",
                borderRadius: 8,
                cursor: "pointer",
                border: "1px solid #3a3c40",
              }}
            >
              Choose File
              <input type="file" accept="image/*" onChange={onPick} style={{ display: "none" }} />
            </label>

            <button
              onClick={analyze}
              disabled={!file || status === "Analyzing..."}
              style={{
                background: status === "Analyzing..." ? "#2d5db3" : "#3b82f6",
                border: "none",
                color: "white",
                padding: "8px 14px",
                borderRadius: 8,
                cursor: !file ? "not-allowed" : "pointer",
                opacity: !file ? 0.6 : 1,
              }}
            >
              {status === "Analyzing..." ? "Analyzing..." : "Analyze"}
            </button>

            <span style={{ opacity: 0.8 }}>{file ? file.name : "No file selected"}</span>
          </div>

          <div
            style={{
              marginTop: 16,
              padding: 14,
              border: "1px dashed #3a3c40",
              borderRadius: 10,
              opacity: 0.9,
            }}
          >
            Tip: you can also drag & drop an image anywhere on this page.
          </div>

          {imgUrl && (
            <div style={{ marginTop: 20 }}>
              <img
                src={imgUrl}
                alt="preview"
                style={{ maxWidth: "100%", borderRadius: 12, border: "1px solid #303236" }}
              />
            </div>
          )}

          {error && (
            <div
              style={{
                marginTop: 16,
                padding: 12,
                background: "#3a1d1d",
                border: "1px solid #5d2a2a",
                borderRadius: 8,
                color: "#ffd7d7",
                whiteSpace: "pre-wrap",
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Right column: results */}
        <div>
          <div
            style={{
              background: "#222327",
              border: "1px solid #2f3136",
              borderRadius: 12,
              padding: 16,
              minHeight: 120,
              marginBottom: 16,
            }}
          >
            <h2 style={{ marginTop: 0, marginBottom: 8 }}>Status</h2>
            <div>{status}</div>
          </div>

          <div
            style={{
              background: "#222327",
              border: "1px solid #2f3136",
              borderRadius: 12,
              padding: 16,
              marginBottom: 16,
            }}
          >
            <h2 style={{ marginTop: 0, marginBottom: 8 }}>Prediction</h2>
            {result ? (
              <div style={{ lineHeight: 1.7 }}>
                <div>
                  <strong>Class:</strong> {result?.ml?.class ?? "—"}
                </div>
                <div>
                  <strong>Confidence:</strong>{" "}
                  {result?.ml?.confidence != null ? (result.ml.confidence * 100).toFixed(1) + "%" : "—"}
                </div>
                <div>
                  <strong>Latency:</strong> {result?.ml?.latency_ms ?? "—"} ms
                </div>
                <div>
                  <strong>Model:</strong> {result?.ml?.model_version ?? "—"}
                </div>
              </div>
            ) : (
              <div style={{ opacity: 0.8 }}>No result yet.</div>
            )}
          </div>

          <div
            style={{
              background: "#222327",
              border: "1px solid #2f3136",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <h2 style={{ marginTop: 0, marginBottom: 8 }}>Auto-generated Report (Markdown)</h2>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                fontSize: 14,
                margin: 0,
                color: "#ddd",
              }}
            >
              {result?.report?.markdown || "—"}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
