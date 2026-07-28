# scripts/download_cwru.py
# CWRU 12kHz 驱动端数据下载脚本
# 策略:优先从官方 case.edu 按文件编号下载 .mat;给出失败时的手动指引
import os
import urllib.request

RAW_DIR = "data/raw"

# CWRU 官方文件编号(12kHz 驱动端,0.007英寸故障,0负载/1797rpm)
# 正常=97, 内圈=105, 外圈(@6点钟)=130, 滚动体=118
FILES = {
    "normal.mat": "97",
    "inner.mat":  "105",
    "outer.mat":  "130",
    "ball.mat":   "118",
}

# 官方下载地址模板(文件编号 .mat)
BASE_URLS = [
    "https://engineering.case.edu/sites/default/files/{num}.mat",
    "https://csegroups.case.edu/sites/default/files/bearingdatacenter/files/Datafiles/{num}.mat",
]


def download_one(fname, num):
    out_path = os.path.join(RAW_DIR, fname)
    if os.path.exists(out_path):
        print(f"[已存在] {fname},跳过")
        return True
    for base in BASE_URLS:
        url = base.format(num=num)
        try:
            print(f"尝试下载 {fname} <- {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(out_path, "wb") as f:
                f.write(r.read())
            size = os.path.getsize(out_path) / 1024
            if size < 10:  # 太小说明下到的是错误页面
                os.remove(out_path)
                print(f"  下载内容异常(仅{size:.1f}KB),换下一个源")
                continue
            print(f"  成功,{size:.1f} KB")
            return True
        except Exception as e:
            print(f"  失败: {e}")
    return False


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    failed = []
    for fname, num in FILES.items():
        ok = download_one(fname, num)
        if not ok:
            failed.append((fname, num))

    print("\n" + "=" * 50)
    if not failed:
        print("全部下载完成,文件在 data/raw/ 下")
    else:
        print("以下文件自动下载失败,请手动下载:")
        for fname, num in failed:
            print(f"  - {fname}: 到 https://engineering.case.edu/bearingdatacenter/download-data-file")
            print(f"    找文件编号 {num}.mat,下载后重命名为 {fname} 放到 data/raw/")


if __name__ == "__main__":
    main()