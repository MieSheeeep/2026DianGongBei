"""读取附件 1-8 的 Excel 数据，把它们转为干净的 numpy 数组。

约定：所有 24 小时序列长度都是 24，索引 h 对应时段 [h, h+1)；
功率单位 MW，电量单位 MWh，电价单位 元/kWh。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent / "A题"

FN_LOAD = "附件1：园区典型日常规电负荷标幺功率曲线.xlsx"
FN_TYPICAL = "附件2:典型日风电、光伏标幺功率表.xlsx".replace(":", "：")
FN_WIND_SCN = "附件3：园区6种场景的风电标幺功率表.xlsx"
FN_PV_SCN = "附件4：园区4种场景的光伏标幺功率表.xlsx"


def _read_24h_matrix(fname: str, ncols: int) -> np.ndarray:
    """读 (25 行 × (1+ncols) 列) 的表，扔掉表头行 + 时段列，返回 (24, ncols) float。"""
    df = pd.read_excel(BASE_DIR / fname, header=None)
    arr = df.iloc[1:, 1:].to_numpy(dtype=float)
    assert arr.shape == (24, ncols), f"{fname}: expected (24, {ncols}), got {arr.shape}"
    return arr


def load_typical_load() -> np.ndarray:
    """附件 1：常规负荷标幺，shape (24,)。"""
    return _read_24h_matrix(FN_LOAD, 1)[:, 0]


def load_typical_wind_pv() -> tuple[np.ndarray, np.ndarray]:
    """附件 2：典型日风电、光伏标幺，两个 (24,) 向量。"""
    arr = _read_24h_matrix(FN_TYPICAL, 2)
    return arr[:, 0], arr[:, 1]


def load_wind_scenarios() -> np.ndarray:
    """附件 3：6 个风电场景标幺，shape (24, 6)。"""
    return _read_24h_matrix(FN_WIND_SCN, 6)


def load_pv_scenarios() -> np.ndarray:
    """附件 4：4 个光伏场景标幺，shape (24, 4)。"""
    return _read_24h_matrix(FN_PV_SCN, 4)


if __name__ == "__main__":
    print("load:", load_typical_load().shape)
    w, p = load_typical_wind_pv()
    print("wind:", w.shape, "pv:", p.shape)
    print("wind scenarios:", load_wind_scenarios().shape)
    print("pv scenarios:", load_pv_scenarios().shape)
