# Q3 事实库（论文手入口）

更新日期：2026-09-12（Asia/Shanghai）

## 唯一当前结论

队内当前采用模型为：

`candidate_041_dynamic_open_route_deferred_cross_view`

论文、答辩稿和后续复核应首先使用本目录。`task3/report/`、`task3/strategy_design*.md` 和旧版 `task3/README.md` 中涉及 Geometry、020、038、039、040 的“当前”“冠军”“默认”等表述均只代表当时阶段，不再是最终选型结论。

## 阅读顺序

1. [current_model.md](current_model.md)：最终模型的完整策略、约束和终止条件；
2. [performance.md](performance.md)：可引用性能数据、时间口径和证据边界；
3. [history.md](history.md)：从重构到最终版的关键优化路径及被否决方案；
4. 本文件末尾的产物索引：原始日志、路线图与复现命令。

## 论文可以陈述的结论

- 七点覆盖和硬可行集提供搜索与安全清除的确定性保证；动态 TSP、顺路观测和预挂起交叉观测用于缩短时间。
- 在最终 20 个全新随机源数场景中，041 完成 20/20 场、清除 266/266 个干扰源；总时间除以总源数为 274.32 s/源。
- 另一组 10 个全新随机场景完成 10/10 场、清除 133/133 个源；总时间除以总源数为 275.23 s/源。
- 两批合计 30 场、399 个源，合并口径为 274.62 s/源。
- 固定 16 源的 5 个配对场景中，041 相对 040 的均值从 4065.49 s 降至 4001.87 s，平均改善 63.61 s（1.56%），但其中一个场景回退 115.41 s，不能宣称逐场占优。

## 论文不能越界的结论

- 不能宣称 041 是全局最优路线或对所有场景都优于 040。
- 不能把 5、10、20 个场景的小样本写成大样本统计显著性结论。
- 不能把离线 Mock 的性能直接等同于正式比赛成绩。
- 不能把概率或启发式排序写成正确性证明；正确性来自硬集合、覆盖证书和保守清除条件。
- “平均单源用时”统一采用 `所有场景总虚拟时间 / 所有场景总源数`，不得与“逐场单源用时再平均”混用。

## 权威产物索引

### 最终模型性能

- `task3/results/raw/optimization/dynamic_open_route_041_random20_seed20261016.jsonl.gz`：20 个全新随机源数场景，主性能证据；
- `task3/results/raw/optimization/dynamic_open_route_041_random10_seed20261006.jsonl.gz`：10 个全新随机源数场景，与十张路线图一一对应；
- `task3/results/figures/candidate041_random10_seed20261006/`：最终模型十张独立路线图；
- `task3/results/figures/model_evolution/`：同一种子 0920 的 039、040、041 代表路线；
- `task3/results/figures/candidate038_latest_overview/`：038 重构阶段代表路线；
- `task3/results/raw/optimization/dynamic_open_route_041_detection_audit_seed20261001_5case.jsonl.gz`：检测时间与无效检测审计。

### 关键演进证据

- `task3/results/raw/optimization/task_queue_sweep_038_latest_headless_10case.jsonl.gz`：重构阶段 038 的代表性结果；
- `task3/results/raw/optimization/dynamic_open_route_039_tsp_window_seed20260919_5case_16sources.jsonl.gz`：039 最终窗口版本；
- `task3/results/raw/optimization/dynamic_open_route_039_vs_040_sparse_six_v2_seed20260919_5case_16sources.jsonl.gz`：039 与 040 配对；
- `task3/results/raw/optimization/dynamic_open_route_040_vs_041_deferred_cross_view_final2_seed20260919_5case_16sources.jsonl.gz`：040 与最终 041 配对。

## 最小复现命令

从仓库根目录运行：

```powershell
D:\tools\anaconda3\envs\onn\python.exe -m pytest task3/test -q

D:\tools\anaconda3\envs\onn\python.exe -m task3.experiments.run_offline `
  --cases 20 --seed 20261016 --workers 1 `
  --policies candidate_041_dynamic_open_route_deferred_cross_view `
  --output task3/results/raw/optimization/reproduce_candidate041_random20.jsonl.gz
```

当前完整回归为 112 项通过。Windows 受限环境中使用 `--workers 1`，避免多进程管道权限错误。
