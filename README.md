# Atlas AI — PCB Defect Detection & Auto-Report Platform

End-to-end AI prototype for PCB inspection:
- **ML Service**: FastAPI + PyTorch (ResNet18 classifier over six PCB defect
  categories) with **Grad-CAM weakly-supervised localization** and a
  **Redis** inference cache.
- **LLM Service**: FastAPI report generator that emits Markdown **and a
  downloadable PDF**, with a **severity rating** per defect.
- **API Gateway**: Node.js (Express) orchestrator.
- **Web App**: React + Vite.
- **Docker Compose**: one command brings it all up.

## Pipeline

```
image → gateway → ml-service (classify + Grad-CAM box/overlay, Redis cache)
                → llm-service (severity + Markdown + PDF report)
                → web app (prediction, heatmap overlay, severity badge, PDF download)
```

## Features

### Defect classification (ResNet18)
Six categories: `missing_hole, mouse_bite, open_circuit, short, spur,
spurious_copper`. Returns class, confidence, and inference latency.

### Grad-CAM localization (`box` + `overlay_png_b64`)
The deployed model is a classifier, not a detector. Grad-CAM on the last conv
block (`layer4`) recovers a **weakly-supervised** localization box from where
the network actually reacts, returned as normalized `[x1,y1,x2,y2]` coords plus
a JET heatmap overlay with a green box drawn on the flagged region. The clean
next step is a real detection head.

### Severity ratings
Severity is the defect's functional impact weighted by model confidence.
Connectivity-breaking defects (`short`, `open_circuit`) are **critical**,
connectivity-risking defects (`missing_hole`, `spurious_copper`) are **major**,
marginal/cosmetic defects (`mouse_bite`, `spur`) are **minor**. Confidence below
0.5 is routed to **review** (manual) instead of being auto-rated.

### PDF diagnostic reports
The LLM service renders each report to a downloadable PDF (`fpdf2`, pure-Python)
containing the class, confidence, severity, and recommended actions.

### Redis cache
Inference results are cached by sha256 of the image bytes, so repeat uploads of
the same board skip the model and return `cache_hit: true` with near-zero
latency. Cache failures are non-fatal — the service also runs standalone.

## Prerequisite: trained model

The ml-service needs the trained weights, which are **not committed**:
- `ml-service/app/models/pcb_resnet18.pt`
- `ml-service/app/models/class_names.json`

Train them with `ml-training/train.py` against the Roboflow PCB dataset under
`data/pcb/classification/` (use `ml-training/yolo_to_classification.py` to crop
YOLO annotations into classification inputs first). If your class names differ
from the six above, update `SEVERITY_BY_CLASS` in `llm-service/app/main.py`.

## Run (dev)

```bash
docker-compose up --build
curl localhost:8001/healthz      # ml-service: ok, lists classes
curl localhost:8002/healthz      # llm-service: ok
# open the web app at localhost:3000 and upload a PCB image
```

Optional: set `OPENAI_API_KEY` to have the LLM service write the report prose;
without it, a built-in Markdown template is used.
