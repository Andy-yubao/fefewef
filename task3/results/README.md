# Q3 结果目录说明

当前模型与可引用数字见 `task3/facts/`。本目录保留两类材料：

1. 受版本控制的早期基线、消融和在线演练记录，作为完整研究历史；
2. Candidate 038–041 的精选演进证据与 Candidate 041 最终验证。

当前新增精选原始日志只有：

- `raw/optimization/task_queue_sweep_038_latest_headless_10case.jsonl.gz`
- `raw/optimization/dynamic_open_route_039_tsp_window_seed20260919_5case_16sources.jsonl.gz`
- `raw/optimization/dynamic_open_route_039_vs_040_sparse_six_v2_seed20260919_5case_16sources.jsonl.gz`
- `raw/optimization/dynamic_open_route_040_vs_041_deferred_cross_view_final2_seed20260919_5case_16sources.jsonl.gz`
- `raw/optimization/dynamic_open_route_041_detection_audit_seed20261001_5case.jsonl.gz`
- `raw/optimization/dynamic_open_route_041_random10_seed20261006.jsonl.gz`
- `raw/optimization/dynamic_open_route_041_random20_seed20261016.jsonl.gz`

图像：

- `figures/model_evolution/`：同一种子 0920 的 039、040、041 路线；
- `figures/candidate041_random10_seed20261006/`：最终模型十张随机场景路线；
- `figures/candidate038_latest_overview/`：038 重构阶段代表路线。

汇总表 `tables/candidate041_key_performance.csv` 可供论文制表，但任何数字都应能回溯到上述 gzip JSONL。Candidate 042 已否决，原始重复日志已清理，只在 `task3/facts/history.md` 中保留结论。
