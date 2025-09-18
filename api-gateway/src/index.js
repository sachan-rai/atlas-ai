import express from "express";
import multer from "multer";
import cors from "cors";

const app = express();
app.use(cors({ origin: "*" }));           // dev CORS
const upload = multer({ storage: multer.memoryStorage() });

const ML_URL  = process.env.ML_URL  || "http://ml-service:8001";
const LLM_URL = process.env.LLM_URL || "http://llm-service:8002";
const TIMEOUT_MS = 20000;

function withTimeout(opts = {}) {
  // Node 20 has AbortSignal.timeout
  return { ...opts, signal: AbortSignal.timeout(TIMEOUT_MS) };
}

app.get("/healthz", (_, res) => res.json({ status: "ok" }));

app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: "missing file" });

    // ---- 1) Send image to ML service
    const form = new FormData();
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype || "image/jpeg" });
    const filename = req.file.originalname || "upload.jpg";
    form.append("file", blob, filename);

    const mlResp = await fetch(`${ML_URL}/infer`, withTimeout({ method: "POST", body: form }));
    if (!mlResp.ok) {
      const txt = await mlResp.text().catch(() => "");
      console.error("ML error:", mlResp.status, txt);
      return res.status(502).json({ error: "ml-service error", status: mlResp.status, detail: txt });
    }
    const ml = await mlResp.json();

    // ---- 2) Ask LLM service to write a report
    const llmResp = await fetch(`${LLM_URL}/report`, withTimeout({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        class_name: ml.class,
        confidence: ml.confidence,
        latency_ms: ml.latency_ms,
        image_name: filename
      })
    }));
    if (!llmResp.ok) {
      const txt = await llmResp.text().catch(() => "");
      console.error("LLM error:", llmResp.status, txt);
      return res.status(502).json({ error: "llm-service error", status: llmResp.status, detail: txt, ml });
    }
    const report = await llmResp.json();

    res.json({ ml, report });
  } catch (e) {
    console.error("Gateway /upload error:", e);
    res.status(500).json({ error: "gateway error", detail: String(e) });
  }
});

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => console.log(`API Gateway on http://localhost:${PORT}`));
