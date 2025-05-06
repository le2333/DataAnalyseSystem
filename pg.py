import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import stft, welch

# 1. 加载数据
df = pd.read_csv(
    "data/raw/sat3/5_2025031706435044765.csv",
    header=None,
    names=["timestamp", "value"],
    parse_dates=["timestamp"],
)

# 2. 计算采样周期和采样率
df = df.sort_values("timestamp")
dt = (df["timestamp"].iloc[1] - df["timestamp"].iloc[0]).total_seconds()
fs = 1.0 / dt  # 采样率（Hz）

# 3. 以一天为窗口做STFT
window_sec = 24 * 60 * 60  # 一天的秒数
window_len = int(window_sec / dt)
f, t, Zxx = stft(
    df["value"].values, fs=fs, nperseg=window_len, noverlap=0, boundary=None
)

# 4. 计算每日功率谱密度（Welch方法）
# 先分组
df["date"] = df["timestamp"].dt.date
psd_results = []
for date, group in df.groupby("date"):
    if len(group) < 2:
        continue
    f_psd, pxx = welch(group["value"].values, fs=fs)
    psd_results.append(pd.DataFrame({"date": date, "frequency": f_psd, "psd": pxx}))
psd_df = pd.concat(psd_results, ignore_index=True)

# 5. 可视化时频谱（STFT幅值）
plt.figure(figsize=(12, 6))
plt.pcolormesh(t / 3600, f, np.abs(Zxx), shading="gouraud")
plt.title("STFT 时频谱")
plt.ylabel("频率 (Hz)")
plt.xlabel("时间 (小时)")
plt.colorbar(label="幅值")
plt.tight_layout()
plt.show()

# 6. 可视化每日功率谱密度
plt.figure(figsize=(10, 6))
for date, group in psd_df.groupby("date"):
    plt.plot(group["frequency"], group["psd"], label=str(date))
plt.xlabel("频率 (Hz)")
plt.ylabel("功率谱密度")
plt.title("每日功率谱密度")
plt.legend()
plt.tight_layout()
plt.show()
