# scripts/preprocess.py
import os
import numpy as np
import scipy.io as sio
from sklearn.model_selection import train_test_split

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
SAMPLE_LEN = 1024      # 每个样本的信号长度
STEP = 512             # 滑窗步长(有重叠,增加样本量)

# 文件名 -> 标签。标签顺序要固定,后面工具要用
LABEL_MAP = {
    "normal.mat": 0,   # 正常
    "inner.mat":  1,   # 内圈故障
    "outer.mat":  2,   # 外圈故障
    "ball.mat":   3,   # 滚动体故障
}
CLASS_NAMES = ["正常", "内圈故障", "外圈故障", "滚动体故障"]


def load_signal(mat_path):
    """从 .mat 文件里取出振动信号。CWRU 的变量名形如 X097_DE_time。"""
    mat = sio.loadmat(mat_path)
    # 自动找到包含 'DE_time'(驱动端)的那个变量
    key = [k for k in mat.keys() if "DE_time" in k]
    if not key:
        # 兜底:找最长的那个数值数组
        key = [max((k for k in mat if not k.startswith("__")),
                   key=lambda k: np.size(mat[k]))]
    signal = mat[key[0]].flatten()
    return signal


def slice_signal(signal, label):
    """滑窗切片成多个样本。"""
    samples = []
    for start in range(0, len(signal) - SAMPLE_LEN, STEP):
        seg = signal[start:start + SAMPLE_LEN]
        samples.append(seg)
    X = np.array(samples, dtype=np.float32)
    y = np.full(len(samples), label, dtype=np.int64)
    return X, y


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_X, all_y = [], []
    for fname, label in LABEL_MAP.items():
        path = os.path.join(RAW_DIR, fname)
        if not os.path.exists(path):
            print(f"[跳过] 找不到 {path}")
            continue
        sig = load_signal(path)
        X, y = slice_signal(sig, label)
        print(f"{fname}: 信号长度 {len(sig)}, 切出 {len(X)} 个样本")
        all_X.append(X)
        all_y.append(y)

    X = np.concatenate(all_X)
    y = np.concatenate(all_y)

    # 标准化(按整体均值方差)
    mean, std = X.mean(), X.std()
    X = (X - mean) / (std + 1e-8)
    # 保存标准化参数,工具推理时要用同样的参数
    np.save(os.path.join(OUT_DIR, "norm.npy"), np.array([mean, std]))

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    np.savez(os.path.join(OUT_DIR, "dataset.npz"),
             X_tr=X_tr, y_tr=y_tr, X_te=X_te, y_te=y_te)
    print(f"完成。训练集 {X_tr.shape}, 测试集 {X_te.shape}")


if __name__ == "__main__":
    main()