# 问题 3 固定 16 源离线优化记录

## 结论

本轮只使用本地 `MockSimulator`，没有连接在线演练或正式评测机。固定源数接口已加入 `random_scenario(..., source_count=16)` 和 `run_offline --source-count 16`，省略该参数时仍保持原来的 10--16 随机行为。

历史默认策略仍为 `A_geometry`（注册表中的 `champion_000_geometry_baseline`）。本轮没有候选达到稳定晋级标准：所有候选都只有 smoke/小样本配对结果，未运行完整 development、stability-A/B/C 或 final-holdout，因此不宣称 3500 s 稳定达标，也不把小样本最优候选设为默认。

## 可复现协议

种子集合记录在 `task3/results/raw/optimization/seed_sets.json`。固定 16 源时每个种子生成 16 个互异频道、目标圆域内位置、1000--1500 m 接收半径，并使用位置固定的 SHA-256 有界误差。每个候选在同一场景上运行，结果按案例配对。

快速复现当前 smoke：

```text
task2/.venv/bin/python -m task3.experiments.run_offline --cases 20 --workers 1 --seed 316000 --source-count 16 --policies champion_000_geometry_baseline candidate_001_upper_bound_focus --output task3/results/raw/optimization/candidate_001_smoke.jsonl.gz
```

Windows 沙箱不能创建多进程管道时使用 `--workers 1`；在允许本地进程的环境可使用 `--workers 4`。所有请求/动作仍为串行模拟。

## 当前固定 16 源基线

20 个 smoke 案例、同一组场景配对，所有策略清除率均为 100%，无硬集合异常或非法终止。历史 Geometry 基线均值为 5516.9 s，中位数 5560.3 s，P90 5793.6 s，最大值 6070.1 s。该结果只是 smoke 基线，不是稳定 benchmark。

## 候选迭代与去留

| 策略 | 主要假设 | 样本 | 均值 (s) | 清除率 | 决定 |
|---|---|---:|---:|---:|---|
| `candidate_001_upper_bound_focus` | 发现 16 个频道后停止剩余覆盖动作 | 20 | 5448.9 | 100% | 保留实验记录；配对区间含 0 |
| `candidate_002_grid10` | 10 m 硬外包网格减少冗余测向 | 5 | 5171.7 | 100% | 保留；未满足样本门槛 |
| `candidate_005_grid10_offset250` | 缩短局部交会偏移 | 5 | 5021.7 | 100% | 保留；未满足样本门槛 |
| `candidate_006_grid10_offset750` | 加大局部交会偏移 | 5 | 4948.2 | 100% | 当前小样本最快之一，未晋级 |
| `candidate_007_grid10_coverage_first` | 先完成覆盖再做局部动作 | 5 | 4965.3 | 100% | 保留；未满足样本门槛 |
| `candidate_012_grid10_all_channels` | 不限最近三个已发现频道 | 5 | 4878.2 | 100% | 保留；墙钟和配对样本不足 |
| `candidate_019_grid10_center_approach` | 局部点靠近硬集合中心 | 5 | 4793.9 | 100% | 保留；未满足样本门槛 |
| `candidate_020_grid5_center_approach` | 5 m 网格加中心接近 | 3 | 4781.0 | 100% | smoke 最优线索，不设默认 |
| `candidate_015--018` | 全部历史视线的信息矩阵 | 5 | 7020.5--10037.1 | 100% | 拒绝，路线显著恶化 |
| `candidate_025--027` | 局部点共享其他频道测量 | 5 | 4877.8--5262.5 | 100% | 拒绝，额外测量未抵消移动 |
| `candidate_028--031` | 单元数阈值自适应兜底 | 5 | 5380.3--5813.1 | 100% | 拒绝，兜底落空 15.2--107.4 次 |
| `candidate_032--035` | 覆盖点已发现频道测量门控 | 5 | 5224.7--5488.6 | 100% | 拒绝，省测向时间但移动/兜底恶化 |

完整逐案例原始文件和图表保存在 `task3/results/raw/optimization/`、`task3/results/tables/` 和 `task3/results/figures/`，文件名按实验轮次命名；没有删除失败候选或挑选有利种子。

## 时间瓶颈与证据边界

历史 Geometry smoke 的移动均值约 4345 s，占总虚拟时间 78.8%；检测、切频、光学和激光固定项约 1172 s。路线审计显示单个案例出现约 57 次局部测向决策，最长单次测向移动超过 300 s。因而当前 3500 s 目标需要显著减少局部往返，而不是只调概率权重。上述数字来自固定 16 源 smoke，不外推到稳定总体。

## 正确性与验证

所有代码改动后回归：

```text
task2/.venv/bin/python -m pytest task3/test -q
32 passed
```

硬集合仍为安全方格外包；`no_signal` 只删除 1000 m 必接收圆；清除只接受 MEC 半径不超过 `20 - clear_margin` 的证书或无缝隙有限覆盖；共享测量、路线排序和网格选择均不能删除硬集合或签发清除证书。

## 停止说明

本轮按用户要求在当前实验完成后停止。由于尚未完成 200/100/100/100/500 的稳定协议，不能声称已触发“重大瓶颈停止标准”，也不能声称稳定达到 3500 s。下一次工作应从注册表中的历史 Geometry 基线重新运行完整 development，并在候选达到全部晋级门槛后才考虑替换默认策略。
