import yaml, cv2, pathlib, shutil

ROOT = pathlib.Path("data/pcb/raw")            # YOLOv5 export unzip location
OUT  = pathlib.Path("data/pcb/classification") # where cropped class images will go
OUT.mkdir(parents=True, exist_ok=True)

# 1) read class names from data.yaml (Roboflow/YOLOv5 export provides this)
with open(ROOT/"data.yaml", "r") as f:
    y = yaml.safe_load(f)
names = y["names"] if "names" in y else y["nc"]
name_map = {i: str(n).replace(" ", "_") for i, n in enumerate(names)}

def process_split(split):
    img_dir = ROOT/split/"images"
    lbl_dir = ROOT/split/"labels"
    for lbl in lbl_dir.glob("*.txt"):
        img = img_dir/(lbl.stem + ".jpg")
        if not img.exists():
            img = img_dir/(lbl.stem + ".png")
            if not img.exists():
                continue
        im = cv2.imread(str(img))
        if im is None:
            continue
        h, w = im.shape[:2]
        with open(lbl, "r") as f:
            for i, line in enumerate(f):
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:5])  # normalized [0,1] YOLO format
                # convert normalized center/size -> pixel box
                x1 = int((cx - bw/2) * w)
                y1 = int((cy - bh/2) * h)
                x2 = int((cx + bw/2) * w)
                y2 = int((cy + bh/2) * h)
                # clamp to image bounds
                x1 = max(0, x1); y1 = max(0, y1); x2 = min(w-1, x2); y2 = min(h-1, y2)
                if x2 <= x1 or y2 <= y1:  # skip weird/empty boxes
                    continue
                crop = im[y1:y2, x1:x2]
                out_dir = OUT/split/name_map[cls]
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir/f"{lbl.stem}_{i}.jpg"
                cv2.imwrite(str(out_path), crop)

for split in ["train","valid","test"]:
    process_split(split)



print("Done ->", OUT)
