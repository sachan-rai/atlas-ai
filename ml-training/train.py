import json, pathlib, torch
from torchvision import datasets, transforms, models
from torch import nn, optim
from tqdm import tqdm

def main():
    # --- PATHS ---
    DATA = pathlib.Path("data/pcb/classification")   # <- make sure this exists (train/ valid/ test/)
    MODELS = pathlib.Path("ml-service/app/models"); MODELS.mkdir(parents=True, exist_ok=True)

    # --- TRANSFORMS ---
    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    # Roboflow uses 'valid' instead of 'val'
    val_split = "val" if (DATA/"val").exists() else "valid"

    # --- DATASETS ---
    train_ds = datasets.ImageFolder(DATA/"train",  transform=train_tf)
    val_ds   = datasets.ImageFolder(DATA/val_split, transform=eval_tf)
    test_ds  = datasets.ImageFolder(DATA/"test",   transform=eval_tf)

    # --- DATALOADERS (Windows-safe: num_workers=0) ---
    train_ld = torch.utils.data.DataLoader(train_ds, batch_size=32, shuffle=True,  num_workers=0)
    val_ld   = torch.utils.data.DataLoader(val_ds,   batch_size=32, shuffle=False, num_workers=0)

    # --- MODEL ---
    device = torch.device("cpu")
    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Linear(model.fc.in_features, len(train_ds.classes))
    model.to(device)

    # --- OPTIMIZER / LOSS ---
    crit = nn.CrossEntropyLoss()
    opt = optim.Adam(model.parameters(), lr=1e-3)

    # --- EPOCH LOOP ---
    def run_epoch(loader, train=True):
        model.train(train)
        tot, correct, loss_sum = 0, 0, 0.0
        bar = tqdm(loader, desc="Training" if train else "Validating", leave=False)
        for x, y in bar:
            x, y = x.to(device), y.to(device)
            if train: opt.zero_grad()
            out = model(x)
            loss = crit(out, y)
            if train:
                loss.backward()
                opt.step()
            loss_sum += loss.item() * x.size(0)
            pred = out.argmax(1)
            correct += (pred == y).sum().item()
            tot += x.size(0)
            bar.set_postfix(loss=f"{loss_sum/max(1,tot):.4f}", acc=f"{correct/max(1,tot):.3f}")
        return correct / max(1, tot), loss_sum / max(1, tot)

    best_acc = 0.0
    EPOCHS = 5
    for epoch in range(1, EPOCHS+1):
        tr_acc, tr_loss = run_epoch(train_ld, train=True)
        va_acc, va_loss = run_epoch(val_ld,   train=False)
        print(f"epoch {epoch}/{EPOCHS} | train_acc={tr_acc:.3f} val_acc={va_acc:.3f} train_loss={tr_loss:.4f} val_loss={va_loss:.4f}")
        if va_acc > best_acc:
            best_acc = va_acc
            torch.save(model.state_dict(), MODELS/"pcb_resnet18.pt")
            with open(MODELS/"class_names.json","w") as f:
                json.dump(train_ds.classes, f)
            print(f"  -> saved best model (val_acc={best_acc:.3f})")

    print("Done. Model:", MODELS/"pcb_resnet18.pt")

if __name__ == "__main__":
    # Windows-safe entry point (prevents multiprocessing spawn errors)
    main()
