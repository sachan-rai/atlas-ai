import express from "express";
import cors from "cors";
import fetch from "node-fetch";
import multer from "multer";
import FormData from "form-data";

const app = express();
const upload = multer();

app.use(cors({ origin: "http://localhost:3000" }));

app.get("/healthz", (_req, res) => res.json({ status: "ok" }));

// receive file from web-app, call ML then LLM, return combined result
app.post("/analyze", upload.single("file"), async (req, res) => {
  try {
    // 1) forward to ML service as multipart/form-data
    const form = new FormData();
    form.append("file", req.file.buffer, {
      filename: req.file.originalname || "image.jpg",
      contentType: req.file.mimetype || "application/octet-stream"
    });

    const mlRes = await fetch("http://ml-service:8001/infer", {
      method: "POST",
      body: form,
      headers: form.getHeaders()
    });
    const ml = await mlRes.json();

    // 2) call LLM service with ML output
    const llmRes = await fetch("http://llm-service:8002/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ class_name: ml.class, confidence: ml.confidence })
    });
    const report = await llmRes.json();

    res.json({ ml, report });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "pipeline_failed" });
  }
});

app.listen(8000, () => console.log("API Gateway on http://localhost:8000"));
