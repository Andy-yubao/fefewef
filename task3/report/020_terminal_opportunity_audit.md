# Candidate 020 Terminal Opportunity Audit

## 范围与口径

- 策略：`candidate_020_grid5_center_approach`
- seeds：`321100`--`321109`
- 数据：复用 `task3/results/raw/optimization/020_early_pass_event_audit.jsonl.gz` 中的全部 Scheduler decisions；未重新运行实验
- 统计单位：同一决策中的每个 channel candidate 各记一次；因此同时报告 candidate 数和不同 decision 数
- route-compatible：直接复用 `route_insert_limit_m = 300 m`
- 完整明细：`task3/results/tables/020_terminal_opportunity_audit.csv`

## 总计

| Opportunity | Candidate 总数 | 不同决策数 | Route-compatible | Route-compatible 且选择 SEARCH | Missed seeds | Missed channels |
|---|---:|---:|---:|---:|---:|---:|
| CLEAR | 45 | 27 | 2 | 2 | 2 | 2 |
| Expected-clearable LOCALIZE | 19 | 15 | 1 | 1 | 1 | 1 |

CLEAR 的两个 route-compatible miss 分别来自 seeds `321103`、`321108`，channels `18`、`19`。Expected-clearable LOCALIZE 的唯一 route-compatible miss 来自 seed `321100`、channel `16`。三者没有集中在单个异常 case，但每种类型各自都很稀疏。

作为背景，全部 45 个 CLEAR candidate 分布于 7 个 seed、11 个 channel；全部 19 个 expected-clearable LOCALIZE candidate 分布于 9 个 seed、10 个 channel。稀缺点不是终结候选本身，而是这些候选与下一 coverage leg 同时满足 300 m 插入口径的交集。

## 代表事件

`search_minus_action_s = search_score_s - action_score_s`；负值表示原 Scheduler 的 SEARCH 分数更低。

| 类型 | seed / decision / channel | `Delta_route` (m) | 当前 / 期望证书半径 (m) | `search_minus_action_s` | 选择 |
|---|---|---:|---|---:|---|
| CLEAR | 321108 / 7 / 19 | 0.64 | 16.77 / — | -0.13 | SEARCH |
| Expected-clearable LOCALIZE | 321100 / 6 / 16 | 27.23 | 23.58 / 18.77 | -0.67 | SEARCH |
| CLEAR | 321103 / 6 / 18 | 175.93 | 15.37 / — | -35.19 | SEARCH |

三个事件都满足 300 m route-compatible 口径并被 SEARCH 错过。其中前两个分数几乎打平，但它们各只出现一次；第三个 CLEAR 的原分数仍明显劣于 SEARCH。

## 判断

### CLEAR-only preemption

Route-compatible CLEAR miss 只有 **2 次**，分别覆盖 2 个 seed 和 2 个 channel。按任务给出的 `0--2` 次停止规则，机会不足以支持实现 CLEAR-only route-compatible preemption；停止该方向。

### Expected-clearable LOCALIZE

Route-compatible expected-clearable LOCALIZE miss 只有 **1 次**，来自 1 个 seed 和 1 个 channel，不是系统性模式，也不值得据此实现新策略；停止该方向。

## 最终回答

Scheduler 确实错过过“几乎可以结束一个 channel 且顺路”的机会，但 10-case 全决策范围内只有 **3 个 candidate-event**：2 个 CLEAR、1 个 expected-clearable LOCALIZE。CLEAR 与 expected-clearable LOCALIZE 均未形成足够重复、跨 case 的系统性机会，因此不继续这一优化方向。

## 实现与验证

- 未修改 Scheduler、策略、local planner、coverage route 或其他运行源码。
- 未重新运行任何 case。
- 仅新增只读分析脚本、CSV 和本报告。
- 完整 Q3 测试：37 passed；另有 2 条 pytest cache 写入权限 warning，不影响结果。
