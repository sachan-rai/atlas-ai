from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="LLM Service")

class Inference(BaseModel):
    class_name: str
    confidence: float

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/report")
def report(data: Inference):
    md = (
        "## AI Report\n\n"
        f"**Prediction:** {data.class_name}\n\n"
        f"**Confidence:** {data.confidence*100:.1f}%\n\n"
        "### Suggested Next Steps\n"
        "- Inspect batch\n- Flag unit for re-check\n- Document issue"
    )
    # later: call OpenAI/Cohere here and return their output
    return {"markdown": md, "pdf_url": "/fake.pdf"}
