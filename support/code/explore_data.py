"""临时探查脚本：把 8 份附件的所有 sheet 全表打印到 stdout，便于人工核对数据结构。

仅本地使用（位于 support/code/，已被 .gitignore 排除）。
执行：python support/code/explore_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent / "A题"
FILES = [
    "附件1：园区典型日常规电负荷标幺功率曲线.xlsx",
    "附件2：典型日风电、光伏标幺功率表.xlsx",
    "附件3：园区6种场景的风电标幺功率表.xlsx",
    "附件4：园区4种场景的光伏标幺功率表.xlsx",
    "附件5：风光发电与制氢设备技术参数.xlsx",
    "附件6：储能设备和合成氨装置技术参数.xlsx",
    "附件7：分时电价表.xlsx",
    "附件8：风电、光伏余电上网电价.xlsx",
]


def main() -> int:
    for fname in FILES:
        path = BASE / fname
        print("=" * 90)
        print(f"FILE: {fname}")
        print("=" * 90)
        if not path.exists():
            print(f"  [missing] {path}")
            continue
        xls = pd.ExcelFile(path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            print(f"\n-- sheet: {sheet_name!r}  shape: {df.shape}")
            with pd.option_context(
                "display.max_rows", None,
                "display.max_columns", None,
                "display.width", 240,
                "display.precision", 6,
            ):
                print(df.to_string())
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
