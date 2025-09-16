from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from io import BytesIO
from PIL import Image
import time

app = FastAPI(title="ML Service")

# placeholder "model"—replace with real PyTorch model later
def fake_predict(pil_img: Image.Image):
    # do preprocessing & model inference here
    time.sleep(0.03)  # simulate latency
    return {"class": "defect", "confidence": 0.92}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    content = await file.read()
    img = Image.open(BytesIO(content)).convert("RGB")
    start = time.time()
    pred = fake_predict(img)
    latency_ms = int((time.time() - start) * 1000)
    return JSONResponse({
        "class": pred["class"],
        "confidence": pred["confidence"],
        "latency_ms": latency_ms,
        "model_version": "v0-fake"
    })
