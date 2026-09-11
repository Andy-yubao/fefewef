# Candidate 020 Early-Pass 事件审计

## 范围与口径

- 策略：`candidate_020_grid5_center_approach`
- seeds：`321100`--`321109`，每例固定 16 个 source
- 原始事件口径不变：clear 前曾进入真实 source 的 300 m 邻域、随后离开、最终返回 clear
- 逐事件明细：`task3/results/tables/020_early_pass_event_audit.csv`
- 低绕行界限直接复用既有配置 `route_insert_limit_m = 300 m`，未引入新阈值

为审计真正的 Scheduler 取舍，表中的 `first_entry_*` 保留原事件的首次进入点；A/B/C/D 使用首次离开 300 m 邻域前的最后一个决策点。否则，机器人先在邻域内处理其他目标或继续接近时会被误记为“已经离开”。

## 1. 总分类

| 分类 | 数量 | 解释 |
|---|---:|---|
| A UNKNOWN | 0 | 离开前没有 UNKNOWN 事件 |
| B no candidate | 3 | 已 FOUND，但该 channel 没有 LOCALIZE/CLEAR candidate |
| C non-missed candidate-present | 12 | 11 个高绕行事件；另 1 个低绕行事件已实际选择该目标的 LOCALIZE |
| D low-detour missed opportunity | 18 | 已 FOUND、有低绕行 LOCALIZE/CLEAR，却选择 SEARCH 离开 |
| **Total** | **33** | 与原始 33 个事件完全一致 |

严格按“高绕行”定义，C 中有 11 个。`321101/channel 11` 的 `Delta_route = 53.84 m`，但 Scheduler 当时实际选择的正是 channel 11 的 LOCALIZE，因此不是 missed opportunity；为保持用户要求的 A/B/C/D 四类总数为 33，将它放入 C 的非 missed 特例，而没有虚增 D。

## 2. B 类拆分

| 原因 | 数量 |
|---|---:|
| `outside_local_shortlist` | 3 |
| `no_local_candidate` | 0 |
| `other` | 0 |

三个事件分别是 `321103/channel 15`、`321104/channel 18`、`321108/channel 15`；都在原点首次进入邻域，channel 已 FOUND，但未进入最近三个 channel 的 local shortlist。因此 B 主要指向 shortlist，而不是 Scheduler score。

## 3. C / D 的路线插入代价

定义：

\[
\Delta_{\mathrm{route}}=\lVert x-a\rVert+\lVert a-c\rVert-\lVert x-c\rVert.
\]

| 集合 | n | Median (m) | P75 (m) | Max (m) |
|---|---:|---:|---:|---:|
| C（含 1 个已处理特例） | 12 | 491.12 | 628.43 | 1300.66 |
| C（仅 11 个高绕行） | 11 | 501.22 | 689.33 | 1300.66 |
| D | 18 | 90.77 | 179.48 | 265.13 |
| C + D | 30 | 187.93 | 431.18 | 1300.66 |

`321105/channel 14` 和 `321107/channel 6` 离开时 coverage 已完成，故 `next_coverage_position` 如实留空；这两个事件只用当前实际选中的下一动作点作为插入参照，`Delta_route` 分别为 567.53 m 和 501.22 m，均归 C，不影响 D 的数量或分布。

代表事件：

| seed / channel | 类别 | 距真实 source (m) | candidate | `Delta_route` (m) | expected radius (m) | Scheduler 选择 |
|---|---|---:|---|---:|---:|---|
| 321108 / 19 | D | 96.68 | CLEAR | 0.64 | — | SEARCH |
| 321100 / 16 | D | 22.04 | LOCALIZE | 27.23 | 18.77 | SEARCH |
| 321101 / 11 | C 特例 | 180.65 | LOCALIZE | 53.84 | 500.25 | 同一 channel 的 LOCALIZE |
| 321105 / 14 | C | 290.65 | LOCALIZE | 567.53 | 23.08 | channel 16 CLEAR；无剩余 coverage |
| 321102 / 14 | C | 64.38 | LOCALIZE | 1300.66 | 424.18 | SEARCH |

## 4. LOCALIZE completion

- 33 个 early-pass 中，28 个在离开决策点已有该 channel 的 LOCALIZE candidate；另有 2 个已有 CLEAR candidate，3 个无 candidate。
- 28 个 LOCALIZE 中，仅 **1 个**满足 `candidate_expected_radius_m <= clear_threshold_m`。
- clear threshold 为 `20 - 0.25 = 19.75 m`。
- 唯一 expected-clearable 事件是 `321100/channel 16`：当前证书半径 23.58 m，候选期望半径 18.77 m，`Delta_route = 27.23 m`，Scheduler 选择 SEARCH。

因此，D 中虽然有 17 个 LOCALIZE 机会，但其中 16 个预计一次测量后仍不能直接 CLEAR；低绕行不等价于低完成成本。

## 5. 结论

真正属于“已经知道目标、存在低额外路线代价的可执行 LOCALIZE/CLEAR，却仍然离开”的事件是 **18 / 33（54.5%）**。其中 17 个是 LOCALIZE、1 个是 CLEAR；18 个共同表现为在仍有 coverage 时选择 SEARCH。

D 数量明显，不支持“020 的视觉回头多数都只是无信息经过”的判断，Scheduler 机会仍值得研究。但现有证据也不支持再次使用简单的 proximity/defer 权重：17 个 LOCALIZE 中只有 1 个预计一步可 clear，而且 candidate 036 已在闭环实验中增加 movement。后续若继续，应围绕多步完成成本与明确 CLEAR 机会做针对性设计，而不是扩大 shortlist 或无差别抢占 coverage。本任务未实现任何新策略。

## 6. 行为保持与测试

- 新审计运行与原 10-case 记录逐 seed 的 virtual time、动作数及完整动作签名全部一致。
- 针对性测试：7 passed。
- 完整 Q3 测试：37 passed；另有 2 条 pytest cache 写入权限 warning，不影响测试结果。
