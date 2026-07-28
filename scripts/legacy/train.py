# scripts/train.py
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
NUM_CLASSES = 4
EPOCHS = 30
BATCH = 64


class LightCNN(nn.Module):
    """1D 轻量 CNN,参数量很小,适合边缘部署。"""
    def __init__(self, num_classes=NUM_CLASSES):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=15, stride=2, padding=7),
            nn.BatchNorm1d(16), nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(16, 32, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm1d(32), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.fc = nn.Linear(32, num_classes)

    def forward(self, x):
        x = x.unsqueeze(1)          # (B, L) -> (B, 1, L)
        x = self.net(x)             # (B, 32, 1)
        x = x.flatten(1)            # (B, 32)
        return self.fc(x)


def main():
    data = np.load("data/processed/dataset.npz")
    X_tr = torch.tensor(data["X_tr"])
    y_tr = torch.tensor(data["y_tr"])
    X_te = torch.tensor(data["X_te"])
    y_te = torch.tensor(data["y_te"])

    tr_loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=BATCH, shuffle=True)
    te_loader = DataLoader(TensorDataset(X_te, y_te), batch_size=BATCH)

    model = LightCNN().to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"模型参数量: {n_params}")

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()

    for ep in range(EPOCHS):
        model.train()
        for xb, yb in tr_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            opt.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            opt.step()

        # 每轮评估
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for xb, yb in te_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                pred = model(xb).argmax(1)
                correct += (pred == yb).sum().item()
                total += yb.size(0)
        acc = correct / total
        print(f"Epoch {ep+1:2d} | loss {loss.item():.4f} | test acc {acc:.4f}")

    torch.save(model.state_dict(), "models/bearing_cnn.pth")
    print(f"模型已保存,最终测试准确率 {acc:.4f}")


if __name__ == "__main__":
    main()