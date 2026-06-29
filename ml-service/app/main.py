from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from io import BytesIO
from PIL import Image
import time, json, base64
import numpy as np
import cv2
import torch
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

# ---- Grad-CAM hooks on the last conv block (ResNet18 layer4) ----
# The deployed model is a classifier, not a detector. Grad-CAM recovers a
# weakly-supervised localization box from where the network actually reacts,
# so the inspector still gets a region on the board without training a detector.
_acts, _grads = {}, {}
model.layer4.register_forward_hook(lambda m, i, o: _acts.__setitem__("v", o))
model.layer4.register_full_backward_hook(lambda m, gi, go: _grads.__setitem__("v", go[0].detach()))

OVERLAY_MAX_SIDE = 640  # cap overlay resolution so the base64 payload stays reasonable


def gradcam_and_box(x, class_idx, orig_rgb):
    """Run a grad-enabled pass, build the CAM for class_idx, and return a
    normalized [0,1] bounding box of the activated region plus a base64 PNG
    overlay (JET heatmap blended over the original with a green box)."""
    model.zero_grad()
    out = model(x)                       # grad-enabled, NOT under no_grad
    out[0, class_idx].backward()
    acts = _acts["v"][0]                 # [C,h,w]
    grads = _grads["v"][0]               # [C,h,w]
    w = grads.mean(dim=(1, 2))
    cam = torch.relu((w[:, None, None] * acts).sum(0))
    cam = (cam / (cam.max() + 1e-8)).detach().cpu().numpy()

    H, W = orig_rgb.shape[:2]
    cam = cv2.resize(cam, (W, H))
    ys, xs = np.where(cam >= 0.5)
    box = (
        [float(xs.min() / W), float(ys.min() / H), float(xs.max() / W), float(ys.max() / H)]
        if len(xs)
        else None
    )

    heat = cv2.applyColorMap((cam * 255).astype(np.uint8), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(cv2.cvtColor(orig_rgb, cv2.COLOR_RGB2BGR), 0.6, heat, 0.4, 0)
    if box:
        cv2.rectangle(overlay, (int(xs.min()), int(ys.min())), (int(xs.max()), int(ys.max())), (0, 255, 0), 2)
    ok, buf = cv2.imencode(".png", overlay)
    return box, base64.b64encode(buf.tobytes()).decode()


@app.get("/healthz")
def health():
    return {"status": "ok", "model": "pcb_resnet18", "classes": class_names, "device": str(device)}


@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    content = await file.read()
    img = Image.open(BytesIO(content)).convert("RGB")

    # Original image (downscaled) used for the heatmap overlay.
    orig = np.array(img)
    h, w = orig.shape[:2]
    scale = OVERLAY_MAX_SIDE / max(h, w)
    if scale < 1.0:
        orig = cv2.resize(orig, (int(w * scale), int(h * scale)))

    x = preprocess(img).unsqueeze(0).to(device)

    # Classification forward pass (timed: this is the "inference" latency).
    start = time.time()
    out = model(x)
    probs = torch.nn.functional.softmax(out, dim=1)[0]
    conf, idx = torch.max(probs, 0)
    latency_ms = int((time.time() - start) * 1000)
    class_idx = int(idx)

    # Weakly-supervised localization (separate from the classification latency).
    box, overlay_b64 = gradcam_and_box(x, class_idx, orig)

    return JSONResponse({
        "class": class_names[class_idx],
        "confidence": float(conf.detach()),
        "latency_ms": latency_ms,
        "model_version": "pcb_resnet18",
        "box": box,                       # normalized [x1,y1,x2,y2] or null
        "overlay_png_b64": overlay_b64,
    })
