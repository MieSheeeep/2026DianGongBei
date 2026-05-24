"""A 题常量配置。

数值来源：赛题说明及附件 5/6/7/8。
"""

from __future__ import annotations


# ---- 装机容量（A题.pdf） ----
WIND_CAPACITY_MW = 40.0   # 风电装机
PV_CAPACITY_MW = 64.0     # 光伏装机
LOAD_PEAK_MW = 6.0        # 常规电负荷峰值

# ---- 制氢氨设备（问题一初始额定值；扩容时随产能线性同步提升） ----
ALK_CAPACITY_MW = 10.0    # 碱性电解槽 ALKEL
ALK_H2_RATE_KGH = 140.0   # kg H2/h
PEM_CAPACITY_MW = 10.0    # 质子交换膜电解槽 PEMEL
PEM_H2_RATE_KGH = 160.0   # kg H2/h
NH3_CAPACITY_MW = 0.75    # 合成氨装置
NH3_RATE_TPH = 1.5        # t NH3/h（对应日产 36 t）

# ---- 制氢/合成氨工艺常数（附件 5、6） ----
H2_KWH_PER_KG_NOMINAL = 50.0   # 制氢额定耗电（未考虑效率），kWh/kg
ALK_EFFICIENCY = 0.70
PEM_EFFICIENCY = 0.80
NH3_ELEC_KWH_PER_KGNH3 = 0.5
NH3_H2_KG_PER_KGNH3 = 0.2

# ---- 度电成本 / 运维系数（附件 5、6） ----
WIND_LCOE_YUAN_PER_KWH = 0.15   # 风机度电成本（含投资折旧）
PV_LCOE_YUAN_PER_KWH = 0.12     # 光伏度电成本
ALK_OPEX_YUAN_PER_KWH = 0.10    # ALK 运维系数（按用电计）
PEM_OPEX_YUAN_PER_KWH = 0.15    # PEM 运维系数
NH3_OPEX_YUAN_PER_KWH = 0.002   # 合成氨运维（按用电计）
ESS_OPEX_YUAN_PER_KWH = 0.01    # 储能运维

# ---- 储能（附件 6，问题四会用） ----
ESS_CAPEX_YUAN_PER_KWH = 1000.0
ESS_LIFETIME_YR = 15
ESS_CHARGE_EFF = 0.90
ESS_DISCHARGE_EFF = 0.90
ESS_SELF_LOSS_RATE_PER_H = 0.002  # 0.2 %/h

# ---- 合成氨装置投资（附件 6，按 kg/h H2 配额计价） ----
NH3_CAPEX_YUAN_PER_KGH_H2 = 60000.0
NH3_LIFETIME_YR = 30

# ---- 寿命（附件 5） ----
WIND_LIFETIME_YR = 25
PV_LIFETIME_YR = 25
ALK_LIFETIME_YR = 30
PEM_LIFETIME_YR = 30

# ---- 分时购电电价（附件 7） ----
PRICE_PEAK = 0.8024       # 元/kWh，10:00-15:00、18:00-21:00
PRICE_FLAT = 0.6074       # 元/kWh，07:00-10:00、15:00-18:00、21:00-23:00
PRICE_VALLEY = 0.3424     # 元/kWh，23:00-次日07:00


def buy_price_schedule() -> list[float]:
    """返回 24 小时购电电价（元/kWh）。索引 h 对应时段 [h, h+1)。"""
    sched: list[float] = [0.0] * 24
    for h in range(24):
        if h == 23 or h < 7:                              # 低谷 23-07
            sched[h] = PRICE_VALLEY
        elif (10 <= h < 15) or (18 <= h < 21):            # 高峰
            sched[h] = PRICE_PEAK
        elif (7 <= h < 10) or (15 <= h < 18) or (21 <= h < 23):  # 平时
            sched[h] = PRICE_FLAT
        else:
            raise AssertionError(f"unmapped hour {h}")
    return sched


# ---- 余电上网电价（附件 8，风光统一） ----
SELL_PRICE_YUAN_PER_KWH = 0.3779
