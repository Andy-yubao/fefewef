# 论文附件代码

本目录是依据 `paper/final_paper_restructured_draft.md` 整理的精简版，保留论文实际使用的模型、保证条件和结果复算入口。历史候选策略、调参过程、绘图脚本和未进入论文的功能均未收录。

## 文件

- `geometry.py`：±1° 示向半平面、多站交会、目标圆解析裁剪、区域直径和最小包围圆（Q1，也被 Q3/Q4 复用）。
- `active.py`：GDOP Mean、Geometry、FIM E-optimal、Random，以及统一的 250→100→50 m 粗到细选点（Q2）。FIM 和接收半径样本只用于排序。
- `search.py`：Q3 七点覆盖、5 m 保守方格、全向负观测更新、MEC 清除证书、终止条件；Q4 25 点双环、定向负观测禁删、50 m 认证圆和十点光学环；另含开放路线和完成代价原语。
- `reproduce.py`：从原始 CSV/JSONL 日志复算论文的主要数值，并验证几何常数。

上述 Python 文件合计保持为四个，适合合并排入论文附录。`search.py` 有意把硬保证与软路线分开：路线评分只能决定先后顺序，不能删除硬可行方格、放宽清除半径或改变终止证书。

## 运行

建议 Python 3.11+。精简代码的唯一第三方依赖是 NumPy：

```bash
python -m pip install "numpy>=1.26,<3"
python code/reproduce.py --strict
```

仓库当前已有可用环境时，也可直接运行：

```bash
task2/.venv/bin/python code/reproduce.py --strict
```

`--strict` 检查 Q1 反例、Q3/Q4 几何常数、Q2 论文表快照、Q3 的 30/100 场结果、Q4 的 1000 例验证和 3000 次受控运行。命令只读取数据并向标准输出打印 JSON，不修改仓库。

## 数据来源与证据边界

复算入口读取以下已有数据：

- Q2：`task2/results/raw/evaluations.csv` 和 `task2/results/tables/strategy_summary.csv`；
- Q3：`task3/results/tables/optimization_validation/summary.csv` 与 `results/candidate057_concurrency100_seed20261310.jsonl.gz`；
- Q4：`experiments/t4_analysis/outputs/toward6000_v2/*/cases.csv` 与 `results/task4_sensitivity_analysis/controlled_experiment/raw_cases.csv`。

Q1、七点覆盖和十点光学环可由本目录独立复算。Q2/Q3/Q4 的完整随机场景重跑仍依赖原仓库的模拟器和历史实验配置；为避免把数千行接口、模拟器和候选策略塞入论文附件，本目录只提供最终模型核心和对已归档原始日志的聚合复算。因此，离开原仓库数据后，可以复算几何保证和运行模型函数，但不能凭这四个文件重新生成论文全部 Monte Carlo 日志。

还需特别注意：Q2 的当前原始文件生成时间晚于论文采用的 `strategy_summary.csv`，两者并不一致。论文中的 GDOP Mean 均值 52.38 m 来自较早的表格快照；当前 `evaluations.csv` 直接聚合为 48.96 m。`reproduce.py` 同时输出 `raw_current`、`paper_table_snapshot` 和 `consistent=false`，不会掩盖这一数据版本问题。正式定稿前应选择同一批次重新生成 Q2 表格，或在论文中明确采用的批次与 manifest。
