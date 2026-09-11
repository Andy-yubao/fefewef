# Candidate 020 Movement / Localization Chain Audit

## 范围与口径

- 策略：`candidate_020_grid5_center_approach`
- seeds：`321100`--`321109`，每个 case 固定 16 个 source
- 数据：复用 `task3/results/raw/optimization/020_early_pass_event_audit.jsonl.gz` 的动作与 decision 日志；未重新运行实验
- movement 按产生该移动的 Scheduler decision 分为 `SEARCH`、`LOCALIZE`、`CLEAR`；同点 immediate clear 的移动归于带来该移动的 `LOCALIZE` 或 `SEARCH`，其 `CLEAR` movement 为 0
- 距离按模拟器速度 `5 m/s` 由 movement time 换算
- source chain 按 `seed + channel`，从 `per_channel_timing` 读取首次 FOUND 与最终 CLEAR 时刻；计入其间该 channel 的全部 LOCALIZE 和 CLEAR decision（包括失败后重试）
- source 明细：`task3/results/tables/020_movement_localization_chain_audit.csv`

## 1. Movement decomposition

每格为 `movement time (s) / distance (m)`。

| Seed | SEARCH | LOCALIZE | CLEAR | Total |
|---:|---:|---:|---:|---:|
| 321100 | 1040.139 / 5200.69 | 2243.930 / 11219.65 | 541.998 / 2709.99 | 3826.066 / 19130.33 |
| 321101 | 1300.549 / 6502.75 | 2334.108 / 11670.54 | 52.515 / 262.58 | 3687.173 / 18435.86 |
| 321102 | 1440.000 / 7200.00 | 2152.036 / 10760.18 | 113.605 / 568.02 | 3705.641 / 18528.20 |
| 321103 | 1440.000 / 7200.00 | 1219.159 / 6095.79 | 967.980 / 4839.90 | 3627.139 / 18135.69 |
| 321104 | 1440.000 / 7200.00 | 2198.406 / 10992.03 | 201.427 / 1007.13 | 3839.833 / 19199.16 |
| 321105 | 1440.000 / 7200.00 | 1916.103 / 9580.52 | 28.693 / 143.46 | 3384.796 / 16923.98 |
| 321106 | 1274.875 / 6374.38 | 1883.923 / 9419.61 | 112.664 / 563.32 | 3271.462 / 16357.31 |
| 321107 | 1440.000 / 7200.00 | 1138.535 / 5692.68 | 189.770 / 948.85 | 2768.305 / 13841.52 |
| 321108 | 1297.998 / 6489.99 | 1817.431 / 9087.16 | 708.250 / 3541.25 | 3823.680 / 19118.40 |
| 321109 | 1145.494 / 5727.47 | 2207.066 / 11035.33 | 329.963 / 1649.82 | 3682.524 / 18412.62 |
| **Mean** | **1325.906 / 6629.53** | **1911.070 / 9555.35** | **324.687 / 1623.43** | **3561.662 / 17808.31** |
| **Median** | **1370.275 / 6851.37** | **2034.070 / 10170.35** | **195.598 / 977.99** | **3684.848 / 18424.24** |
| **占 mean total** | **37.23%** | **53.66%** | **9.12%** | **100.00%** |

LOCALIZE 是三类中最大的 movement 项，但不是压倒性单项：SEARCH 仍占 37.23%，CLEAR 仅占 9.12%。逐 case 的三项之和均与原始 `time_breakdown.movement_s` 一致，最大绝对误差为 `1.36e-12 s`。

## 2. LOCALIZE 次数分布与集中度

| LOCALIZE 次数 | Source 数 | 占 160 个 source | LOCALIZE movement (m) | 占全部 LOCALIZE movement |
|---:|---:|---:|---:|---:|
| 0 | 15 | 9.38% | 0.00 | 0.00% |
| 1 | 108 | 67.50% | 64940.04 | 67.96% |
| 2 | 11 | 6.88% | 8363.59 | 8.75% |
| 3 | 5 | 3.12% | 3336.92 | 3.49% |
| 4+ | 21 | 13.12% | 18912.94 | 19.79% |

不存在 movement 集中于少数多次 LOCALIZE 的明显 chain。`4+` source 虽有 21 个，但只贡献 19.79% 的 LOCALIZE movement；相反，108 个只做 1 次 LOCALIZE 的 source 贡献 67.96%。按 LOCALIZE distance 排名前 10 的 source 合计也只占 16.35%。主要模式是大量分散的一次性长移动，而非少数反复 localization 的异常 source。

## 3. Top 10 高成本 source

| Rank | Seed | Channel | LOCALIZE count | LOCALIZE distance (m) | CLEAR distance (m) | FOUND -> CLEAR (s) | LOCALIZE source 类型 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 321104 | 6 | 2 | 1811.96 | 0.00 | 2937.43 | `chebyshev_center:1; mec_center:1` |
| 2 | 321109 | 19 | 2 | 1704.08 | 0.00 | 1945.29 | `centroid:1; mec_center:1` |
| 3 | 321108 | 7 | 4 | 1618.25 | 7.96 | 1959.84 | `centroid:2; chebyshev_center:1; mec_center:1` |
| 4 | 321103 | 3 | 5 | 1606.00 | 10.77 | 3064.32 | `chebyshev_center:3; mec_center:2` |
| 5 | 321102 | 16 | 1 | 1584.43 | 10.00 | 4132.17 | `mec_center:1` |
| 6 | 321109 | 5 | 1 | 1533.01 | 10.00 | 4531.27 | `mec_center:1` |
| 7 | 321104 | 2 | 1 | 1481.29 | 0.00 | 3393.36 | `mec_center+task2_geometry:1` |
| 8 | 321109 | 13 | 1 | 1443.60 | 10.61 | 4084.31 | `mec_center:1` |
| 9 | 321107 | 8 | 1 | 1429.40 | 9.70 | 2542.72 | `chebyshev_center:1` |
| 10 | 321102 | 12 | 1 | 1410.56 | 0.00 | 4073.35 | `mec_center:1` |

Top 10 中 6 个仅 LOCALIZE 1 次，进一步反驳“少数长 chain 主导总 movement”的假设。FOUND -> CLEAR elapsed time 很长也不等于该 source 自身持续移动；其中包含等待其他 SEARCH / LOCALIZE / CLEAR action 的时间。

## 4. Center 类型统计

按 decision 日志中的原始 `source` 标签统计，不合并带 `task2_*` 后缀的变体。

| LOCALIZE source | 次数 | Movement time (s) | Movement distance (m) | 平均 distance / action (m) | 占 LOCALIZE movement |
|---|---:|---:|---:|---:|---:|
| `mec_center` | 95 | 8542.91 | 42714.54 | 449.63 | 44.70% |
| `chebyshev_center` | 82 | 6267.55 | 31337.77 | 382.17 | 32.80% |
| `centroid` | 29 | 1926.22 | 9631.12 | 332.11 | 10.08% |
| `mec_center+task2_geometry` | 9 | 1344.58 | 6722.89 | 746.99 | 7.04% |
| `centroid+task2_geometry` | 7 | 748.54 | 3742.71 | 534.67 | 3.92% |
| `chebyshev_center+task2_geometry` | 1 | 166.41 | 832.03 | 832.03 | 0.87% |
| `mec_center+task2_expected_diameter` | 2 | 96.21 | 481.07 | 240.54 | 0.50% |
| `chebyshev_center+task2_e_optimal` | 17 | 18.27 | 91.34 | 5.37 | 0.10% |

`mec_center` 的总 movement 最大，原因同时包含使用次数最多和单次距离偏高；但它只占 LOCALIZE movement 的 44.70%，且高成本 top 10 混有多种 center。现有证据不足以说明反复选择某一种 center 造成了长 chain。

## 5. 发现全部 16 个 source 后的 coverage movement

“首次达到 FOUND + CLEARED = 16”取 16 个真实 source 的 `first_found_virtual_time_s` 最大值；使第 16 个 source 被发现的 SEARCH leg 不算作“之后”。

| Seed | 达到 16 的时刻 (s) | 后续 SEARCH count | 后续 SEARCH distance (m) | 后续 SEARCH time (s) |
|---:|---:|---:|---:|---:|
| 321100 | 2229.76 | 0 | 0 | 0 |
| 321101 | 2204.77 | 0 | 0 | 0 |
| 321102 | 2176.00 | 0 | 0 | 0 |
| 321103 | 1445.00 | 2 | 2400 | 480 |
| 321104 | 1816.00 | 1 | 1200 | 240 |
| 321105 | 2183.00 | 0 | 0 | 0 |
| 321106 | 1831.34 | 1 | 1200 | 240 |
| 321107 | 1822.00 | 1 | 1200 | 240 |
| 321108 | 2202.11 | 0 | 0 | 0 |
| 321109 | 2199.74 | 0 | 0 | 0 |
| **Mean** | — | **0.5** | **600** | **120** |
| **Median** | — | **0** | **0** | **0** |
| **Max** | — | **2** | **2400** | **480** |

只有 4/10 case 在发现全部 16 个 source 后仍有 SEARCH movement；中位数为 0，mean 仅为总 movement time 的 3.37%。因此 020 上确有少量 upper-bound focus 可消除的 coverage movement，但不是稳定或主要瓶颈。

## 6. 最终判断

四种判断中应选择：**已经没有明显单一瓶颈**。

- LOCALIZE movement 最大（53.66%），但没有集中于多次 localization chain：`4+` chain 只占 LOCALIZE movement 的 19.79%，top 10 只占 16.35%，不满足情况 A 的“明显集中”条件。
- CLEAR movement 仅占 9.12%，不满足情况 B。
- 发现全部 source 后的 coverage movement 中位数为 0、只出现在 4/10 case，不足以把 upper-bound focus 认定为情况 C 的主要方向。
- 剩余成本主要分散在 SEARCH 与大量一次性 LOCALIZE 长移动中；仅凭本审计无法给 local planner / center selection、clear ordering 或 upper-bound focus 中任何一个建立足够强的单一优先级。

因此按情况 D 停止：candidate 020 已接近当前架构的局部瓶颈，不继续复杂优化，也不自动实现新策略。

## 实现与验证

- 未修改 Scheduler、local planner、center selection、coverage route 或其他运行源码。
- 未重新运行任何实验 case。
- 新增只读分析脚本、source-level CSV 和本报告。
- 覆盖验证：10 个目标 seed 全部存在；每个 seed 16 个 source，共 160 条唯一 `seed + channel` 记录，无缺失或重复。
- 守恒验证：每个 seed 的 `SEARCH + LOCALIZE + CLEAR` movement 均与原始总 movement 一致，最大绝对误差 `1.36e-12 s`。
- 完整 Q3 测试：`37 passed`；另有 1 条 pytest cache 写入权限 warning，不影响测试结果。
