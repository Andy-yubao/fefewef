# 实验数据字典

## `raw/base_scenarios.csv`

- `scenario_id`：基础场景编号；
- `target_x,target_y`：真实干扰源位置，仅供仿真评价；
- `s1_x,s1_y`：第一次检测点；
- `radius`：真实有效接收半径；
- `radius_mode`：1000/1250/1500 固定或区间随机；
- `error_model`：均匀、截断高斯或最坏有界端点；
- `error1_rad,bearing1_rad`：第一次真实误差与读数。

## `raw/selected_points.csv`

每个基础场景、每种策略一行。含最终第二点、选点目标值、运行时间、搜索候选数、
精确目标评价次数和每级粗到细搜索诊断。

## `raw/evaluations.csv`

每个 `(scenario_id, replicate, strategy)` 一行：第二次结果类型、检测成功标记、
定位区域面积/直径、移动距离/时间、选点运行时间和候选数。所有策略在相同
`(scenario_id, replicate)` 上成对比较。

## `tables/`

- `strategy_summary.csv`：diameter/area 的 mean/median/P75/P90/P95/P99/max，
  三类 outcome、移动距离/时间、runtime、candidate/exact evaluation count；
- `pairwise_comparison.csv`：全部有序策略对的 win rate、均值/中位提升和 95% CI；
- `pairwise_expected_diameter.csv`：ED 对核心 baseline 的 cluster-bootstrap 子表；
- `improvement_vs_random.csv`：相对 random 的子表；
- `sensitivity_error.csv`、`sensitivity_radius.csv`：分层敏感性结果。
- `sensitivity_radius_prior.csv`、`sensitivity_error_model.csv`：规划 prior/权重敏感性；
- `sampling_convergence.csv`、`grid_convergence.csv`：精度、选点稳定性与耗时；
- `ablation_expected_diameter.csv`：coarse-to-fine、hidden-R、pruning 和采样消融；
- `candidate_domain_sensitivity.csv`：目标圆内与理论可检测候选域对照；
- `robustness_geometry_groups.csv`：按 F1/距离/方向四分位分组；
- `representative_cases.csv` 与 `results/case_studies/*.json`：代表案例数值和 WKT 几何。
