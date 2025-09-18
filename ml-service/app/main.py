from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from io import BytesIO
from PIL import Image
import time, json, torch
from torchvision import models, transforms

app = FastAPI(title="ML Service")

# ---- Load model/classes ----
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

with open("models/class_names.json") as f:
    class_names = json.load(f)

model = models.resnet18(weights=None)
model.fc = torch.nn.Linear(model.fc.in_features, len(class_names))
model.load_state_dict(torch.load("models/pcb_resnet18.pt", map_location=device))
model.to(device)
model.eval()

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

@app.get("/healthz")
def health():
    return {"status": "ok", "model": "pcb_resnet18", "classes": class_names, "device": str(device)}

@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    content = await file.read()
    img = Image.open(BytesIO(content)).convert("RGB")
    x = preprocess(img).unsqueeze(0).to(device)

    start = time.time()
    with torch.no_grad():
        out = model(x)
        probs = torch.nn.functional.softmax(out, dim=1)[0]
        conf, idx = torch.max(probs, 0)
    latency_ms = int((time.time() - start) * 1000)

    return JSONResponse({
        "class": class_names[idx],
        "confidence": float(conf),
        "latency_ms": latency_ms,
        "model_version": "pcb_resnet18"
    })
