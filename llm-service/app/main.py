import os, requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="LLM Service")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL     = "https://api.openai.com/v1/chat/completions"
TIMEOUT_SECS   = 30

class Inference(BaseModel):
    class_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    latency_ms: int | None = None
    image_name: str | None = None

def template_report(cls: str, conf: float, latency_ms: int | None, image_name: str | None) -> str:
    return (
        "## PCB Defect Report\n"
        f"**Image:** {image_name or 'N/A'}\n\n"
        f"**Predicted Defect:** {cls}\n\n"
        f"**Confidence:** {conf*100:.1f}%\n\n"
        f"{'**Model Latency:** '+str(latency_ms)+' ms\\n\\n' if latency_ms is not None else ''}"
        "### What this defect means\n"
        "- This category indicates a likely anomaly in the copper trace, pad, or hole geometry.\n"
        "- Such defects can lead to intermittent connections, short circuits, or manufacturing rework.\n\n"
        "### Recommended next actions\n"
        "- Reinspect the flagged region under magnification (optical or AOI).\n"
        "- Validate continuity/isolation with a multimeter or flying probe.\n"
        "- If confirmed, schedule rework or scrap per QA policy and log the defect ID.\n"
    )

def openai_report(cls: str, conf: float, latency_ms: int | None, image_name: str | None) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    prompt = (
        "You are a manufacturing QA assistant. Write a concise Markdown report for a PCB defect.\n\n"
        f"- Image (optional): {image_name or 'N/A'}\n"
        f"- Predicted Defect: {cls}\n"
        f"- Confidence: {conf:.3f}\n"
        f"- Latency (ms): {latency_ms if latency_ms is not None else 'N/A'}\n\n"
        "Include: 1) one short paragraph of meaning, 2) 3–4 actionable next steps, 3) under 160 words."
    )
    try:
        r = requests.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You produce concise, actionable QA reports in Markdown."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 300
            },
            timeout=TIMEOUT_SECS,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return template_report(cls, conf, latency_ms, image_name)

@app.get("/healthz")
def healthz():
    provider = "openai" if OPENAI_API_KEY else "template"
    return {"status": "ok", "provider": provider, "model": OPENAI_MODEL if OPENAI_API_KEY else "markdown-template"}

@app.post("/report")
def report(payload: Inference):
    try:
        if OPENAI_API_KEY:
            md = openai_report(payload.class_name, payload.confidence, payload.latency_ms, payload.image_name)
        else:
            md = template_report(payload.class_name, payload.confidence, payload.latency_ms, payload.image_name)
        return {"markdown": md}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM service error: {e}")
