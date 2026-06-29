import os, base64, requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fpdf import FPDF

app = FastAPI(title="LLM Service")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL     = "https://api.openai.com/v1/chat/completions"
TIMEOUT_SECS   = 30

# ---- Severity model ----
# Severity is the defect's functional impact weighted by model confidence.
# Connectivity-breaking defects are critical, connectivity-risking are major,
# marginal/cosmetic are minor. Below 0.5 confidence we route to human review
# instead of auto-rating, so a low-confidence critical call doesn't auto-escalate.
SEVERITY_BY_CLASS = {
    "short": "critical",
    "open_circuit": "critical",
    "missing_hole": "major",
    "spurious_copper": "major",
    "mouse_bite": "minor",
    "spur": "minor",
}
TIER_WEIGHT = {"critical": 1.0, "major": 0.7, "minor": 0.4, "review": 0.3}


def compute_severity(class_name: str, confidence: float) -> dict:
    key = class_name.lower().replace(" ", "_")
    base = SEVERITY_BY_CLASS.get(key, "major")
    tier = "review" if confidence < 0.5 else base
    score = round(min(1.0, confidence) * TIER_WEIGHT[tier], 3)
    return {"tier": tier, "score": score, "basis": f"{base} class impact x {confidence:.2f} confidence"}


class Inference(BaseModel):
    class_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    latency_ms: int | None = None
    image_name: str | None = None


def template_report(cls: str, conf: float, latency_ms: int | None, image_name: str | None, sev: dict) -> str:
    return (
        "## PCB Defect Report\n"
        f"**Image:** {image_name or 'N/A'}\n\n"
        f"**Predicted Defect:** {cls}\n\n"
        f"**Confidence:** {conf*100:.1f}%\n\n"
        f"**Severity:** {sev['tier'].upper()} (score {sev['score']}, {sev['basis']})\n\n"
        f"{'**Model Latency:** '+str(latency_ms)+' ms\\n\\n' if latency_ms is not None else ''}"
        "### What this defect means\n"
        "- This category indicates a likely anomaly in the copper trace, pad, or hole geometry.\n"
        "- Such defects can lead to intermittent connections, short circuits, or manufacturing rework.\n\n"
        "### Recommended next actions\n"
        f"{'- HOLD for manual review: confidence below auto-rating threshold.\\n' if sev['tier'] == 'review' else ''}"
        "- Reinspect the flagged region under magnification (optical or AOI).\n"
        "- Validate continuity/isolation with a multimeter or flying probe.\n"
        "- If confirmed, schedule rework or scrap per QA policy and log the defect ID.\n"
    )


def openai_report(cls: str, conf: float, latency_ms: int | None, image_name: str | None, sev: dict) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    prompt = (
        "You are a manufacturing QA assistant. Write a concise Markdown report for a PCB defect.\n\n"
        f"- Image (optional): {image_name or 'N/A'}\n"
        f"- Predicted Defect: {cls}\n"
        f"- Confidence: {conf:.3f}\n"
        f"- Severity Tier: {sev['tier']} (score {sev['score']}; basis: {sev['basis']})\n"
        f"- Latency (ms): {latency_ms if latency_ms is not None else 'N/A'}\n\n"
        "State the severity tier explicitly. Include: 1) one short paragraph of meaning, "
        "2) 3-4 actionable next steps (if tier is 'review', the first step must be to hold for "
        "manual review), 3) under 160 words."
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
        return template_report(cls, conf, latency_ms, image_name, sev)


def markdown_to_pdf_bytes(md: str) -> bytes:
    """Render the report Markdown into a simple, readable titled PDF.
    Full Markdown styling is not required; we keep headings/bold/bullets legible
    and stay pure-Python (fpdf2) to avoid system deps in the slim container."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_title("PCB Defect Report")

    def emit(text, size, style="", gap=2):
        pdf.set_font("Helvetica", style, size)
        # fpdf2's core fonts are latin-1; drop anything outside it so we never crash.
        safe = text.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, size * 0.55, safe)
        pdf.ln(gap)

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            pdf.ln(2)
            continue
        if line.startswith("### "):
            emit(line[4:], 13, "B", gap=1)
        elif line.startswith("## "):
            emit(line[3:], 16, "B", gap=2)
        elif line.startswith("# "):
            emit(line[2:], 18, "B", gap=2)
        elif line.startswith("- ") or line.startswith("* "):
            emit("  - " + line[2:].replace("**", ""), 11, "", gap=1)
        else:
            # strip bold markers for body text
            emit(line.replace("**", ""), 11, "", gap=1)

    out = pdf.output()  # fpdf2 returns a bytearray
    return bytes(out)


@app.get("/healthz")
def healthz():
    provider = "openai" if OPENAI_API_KEY else "template"
    return {"status": "ok", "provider": provider, "model": OPENAI_MODEL if OPENAI_API_KEY else "markdown-template"}


@app.post("/report")
def report(payload: Inference):
    try:
        sev = compute_severity(payload.class_name, payload.confidence)
        if OPENAI_API_KEY:
            md = openai_report(payload.class_name, payload.confidence, payload.latency_ms, payload.image_name, sev)
        else:
            md = template_report(payload.class_name, payload.confidence, payload.latency_ms, payload.image_name, sev)
        pdf_b64 = base64.b64encode(markdown_to_pdf_bytes(md)).decode()
        return {"markdown": md, "severity": sev, "pdf_base64": pdf_b64}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM service error: {e}")
