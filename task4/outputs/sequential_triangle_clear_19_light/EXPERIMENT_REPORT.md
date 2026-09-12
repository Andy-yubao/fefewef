# sequential_triangle_clear_19 轻量实验记录

日期：2026-09-12。所有结果来自本地 in-process evaluator；在线策略只使用四个官方接口返回的信息，真值仅在运行结束后用于评分。未执行官方测试。

## 实现边界

- 主搜索骨架固定为 `P1 -> ... -> P19`，相邻点 900 m，完整主骨架 16.2 km。
- 24 个基本三角形显式编号，并按最后访问顶点进入 settlement。
- 每个频道保留全局 bearing/no-signal/attempted/failed-optical 历史；settlement 使用全局 feasible polygon 与新闭合 cell 求交，不建立静态 source-cell 归属。
- 单顶点可见使用每频道每 cell 最多 3 次局部检查；多顶点但区域仍宽使用最多 2 次 cross-view；30 m early optical 失败后有 5 m 中心位移冷却。
- 局部任务用 fixed-start/fixed-end Held-Karp 精确 DP；每次只执行首任务，然后重建并重规划。
- P19 后对已发现 residual/boundary source 做最多 4 次受限处理。圆弓 cap 内从未发现、几乎朝外的定向源仍是明确的风险边界。

## 验证

- 单元与既有测试：35/35 通过。
- 最终固定样本：10 mixed（seed 0--9）、5 all-directional（100--104）、5 all-omni（200--204）。
- 强制回归：257、918、全定向 3917738334，两个策略均 3/3 全清。

## Mixed paired comparison（seed 0--9）

| metric | early_optical_clear_probe | sequential_triangle_clear_19 |
|---|---:|---:|
| all-clear cases | 10/10 | 9/10 |
| mean virtual time (s) | 8291.65 | 8327.19 |
| mean movement (m) | 27448.26 | 33946.95 |
| mean measurements | 461.5 | 249.5 |
| mean no-signal | 422.2 | 197.2 |
| mean local checks | n/a | 30.0 |
| mean main skeleton (m) | n/a | 16200.0 |
| mean local/residual detour (m) | n/a | 17746.95 |

## Stress smoke

| set | baseline all-clear | new all-clear | baseline mean time (s) | new mean time (s) | baseline movement (m) | new movement (m) |
|---|---:|---:|---:|---:|---:|---:|
| all-directional, seeds 100--104 | 5/5 | 3/5 | 9080.13 | 8396.26 | 30379.63 | 33523.30 |
| all-omni, seeds 200--204 | 5/5 | 5/5 | 7821.95 | 7290.28 | 25253.77 | 29460.39 |

Mixed seed 2 and directional seed 102 each contained an unseen outward-facing directional source in a circular boundary cap. Directional seed 103 contained a discovered source that remained unresolved after the bounded residual checks. No all-omni miss occurred.

## Engineering diagnosis

The architecture strongly reduces measurements and no-signal actions, but the first implementation does not convert the 16.2 km skeleton into lower total movement: mean local/residual detour is 17.75 km, taking total movement above the baseline. Directional visible-side reacquisition is the main reliability and movement risk. These results do not justify a 100/300/1000-case expansion yet; the next useful change would be a better visibility-preserving local candidate policy and multi-source settlement batching that reduces return/debt travel, followed by another small paired test.
