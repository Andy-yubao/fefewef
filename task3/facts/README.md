# Q3 事实库（论文手入口）

更新日期：2026-09-13（Asia/Shanghai）

## 唯一当前结论

队内当前采用模型为：

`candidate_057_posterior_free`

Candidate 057 建立在 041 的确定性安全层之上；041 只作为最终配对验证的基线，不再是论文的最终模型。`task3/report/`、`task3/strategy_design*.md` 和旧版 `task3/README.md` 中涉及旧候选的“当前”“冠军”“默认”等表述均只代表当时阶段。

## 阅读顺序

1. [current_model.md](current_model.md)：最终模型的完整策略、约束和终止条件；
2. [performance.md](performance.md)：可引用性能数据、时间口径和证据边界；
3. [history.md](history.md)：从重构到最终版的关键优化路径及被否决方案；
4. 本文件末尾的产物索引：原始日志、路线图与复现命令。

## 论文可以陈述的结论

- 七点覆盖、硬可行集和保守清除证书提供正确性层；完成代价预演、自由覆盖顺序、共享停靠测量、后验排序和有预算试清除只用于缩短时间，不替代证书。
- 最终配对验证（seed 20261210--20261239）中，057 完成 30/30 场、清除 396/396 个源；总虚拟时间/总源数为 **260.80 s/源**，场均 3442.53 s。
- 同场景的 041 为 287.54 s/源、场均 3795.54 s；057 每场均改善，场均节省 353.01 s（26.74 s/源，9.30%）。
- 057 的场景 bootstrap 95% 区间为 248.18--274.47 s/源；这是指定本地模拟分布和这批场景的描述性不确定性，不是官方成绩或全局最优证明。

## 论文不能越界的结论

- 不能宣称 057 是全局最优路线、对未知官方分布的期望最优，或已达到 220 s/源目标。
- 不能把 30 场本地配对验证写成正式比赛成绩或大样本普适性结论；057 与 053 的均值差仅 1.36 s/源，也不应宣称两者已显著不同。
- 不能把离线 Mock 的性能直接等同于正式比赛成绩。
- 不能把概率或启发式排序写成正确性证明；正确性来自硬集合、覆盖证书和保守清除条件。
- “平均单源用时”统一采用 `所有场景总虚拟时间 / 所有场景总源数`，不得与“逐场单源用时再平均”混用。

## 权威产物索引

### 最终模型性能

- `task3/results/raw/optimization/optimization_057_validation30.jsonl.gz`：057 的 30 场最终配对验证原始动作日志；
- `results/candidate057_concurrency100_seed20261310.jsonl.gz`：057 的100场并发规模测试复制件（与原始文件字节一致，省略逐动作轨迹）；
- `results/HANDOFF.md`：该100场测试的配置、汇总指标、SHA-256和适用边界；
- `task3/results/tables/optimization_validation/summary.csv`：041、049、053、057 的统一汇总；
- `task3/results/tables/optimization_validation/paired.csv`：相对 041 的逐场配对改善；
- `task3/results/tables/optimization_best_snapshot.json`：冻结配置、源码哈希、原始日志哈希与回放状态；
- `task3/report/optimization_execution.md`：验证设计、结论边界和复现命令。

### 关键演进证据

- `task3/results/raw/optimization/task_queue_sweep_038_latest_headless_10case.jsonl.gz`：重构阶段 038 的代表性结果；
- `task3/results/raw/optimization/dynamic_open_route_039_tsp_window_seed20260919_5case_16sources.jsonl.gz`：039 最终窗口版本；
- `task3/results/raw/optimization/dynamic_open_route_039_vs_040_sparse_six_v2_seed20260919_5case_16sources.jsonl.gz`：039 与 040 配对；
- `task3/results/raw/optimization/dynamic_open_route_040_vs_041_deferred_cross_view_final2_seed20260919_5case_16sources.jsonl.gz`：040 与最终 041 配对。

## 最小复现命令

从仓库根目录运行：

```powershell
D:\tools\anaconda3\envs\onn\python.exe -m pytest task3/test -q -p no:cacheprovider

D:\tools\anaconda3\envs\onn\python.exe -m task3.experiments.run_offline `
  --cases 30 --seed 20261210 --workers 1 --grid-step 5 `
  --policies candidate_057_posterior_free `
  --output task3/results/raw/optimization/reproduce_candidate057_validation30.jsonl.gz
```

封存时完整回归为 138 项通过；041、049、057 的代表场景逐动作回放一致。Windows 受限环境中使用 `--workers 1`，避免多进程管道权限错误。
