# 提交版支撑材料（冻结候选版）

本目录是论文 `docs/final_paper_restructured_draft.md` 对应的唯一提交源。
它不是研发仓库的完整镜像，而是保留论文 Q1--Q4 所需的最终源代码、实验入口、必要结果快照、配置和测试。

## 独立复现

建议使用 Python 3.11 或更新版本。在本目录根部执行：

```bash
python -m pip install -r requirements.txt
python verify.py
```

`verify.py` 直接调用 `task1`–`task4` 的正式代码并检查封存数据，核验 Q1 几何常数、Q2 当前代码数据、Q3 100 场结果、Q4 五组验证和 3000 次受控实验。它不依赖独立的汇总脚本。

生成纸质附录代码：

```bash
python make_paper_appendix.py
```

输出的 `paper_appendix/code_appendix.md` 只从本目录源代码生成；它是电子支撑材料的核心策略子集，不另行维护。纸质附录有意不收录本地评测机、HTTP 服务、实验分析脚本、测试代码、历史策略和论文未讨论的消融策略。

若要重新运行本地 Q4 小规模模拟：

```bash
python -m task4.cli run --mode local \
  --strategy adaptive_double_ring_clear_probe \
  --seed 42 --output /tmp/submission-q4-seed42.json
```

完整 Q2/Q3/Q4 大样本重跑入口分别位于 `task2/experiments/`、`task3/experiments/` 和 `task4/cli.py`。大样本重跑会产生新的结果，不应直接覆盖本目录中的冻结快照。

## 与论文的对应关系

| 论文部分 | 发布包代码 | 随包数据 |
|---|---|---|
| Q1，硬可行域、圆裁剪、最小包围圆 | `task1/src/q1.py` | 代码内置几何反例 |
| Q2，四种第二检测点策略 | `task2/src/`、`task2/experiments/` | `task2/results/raw/evaluations.csv`、`task2/results/tables/strategy_summary.csv` |
| Q3，七点覆盖和 candidate 057 | `task3/src/`、`task3/experiments/` | `task3/results/raw/optimization/`、`results/candidate057_concurrency100_seed20261310.jsonl.gz` |
| Q4，25 点双环和 Adaptive | `task4/`、`experiments/t4_local/` | `experiments/t4_analysis/outputs/toward6000_v2/`、`results/task4_sensitivity_analysis/` |

## Q2 数据版本

已在提交版中删除 ED，并用四种论文策略重新完成正式实验。当前 `evaluations.csv` 和 `strategy_summary.csv` 来自同一批次，GDOP Mean 均值为 **52.377347 m**，与论文草稿的 **52.38 m** 一致。

实验配置和随机种子记录在 `task2/results/raw/run_manifest.json`；原始逐条结果位于 `task2/results/raw/evaluations.csv`。

Q4 纸面表格使用的是 `candidate` 文件夹中的 `adaptive_double_ring_clear_probe`，基线使用 `baseline` 文件夹中的 `double_ring_optical_clear_probe`；发布包已逐文件核验，避免迁移时误覆盖。

## 维护规则

- 只维护本目录中的源代码；纸质附录应从这里的源文件导出。
- 不把虚拟环境、缓存、历史候选策略和临时 prompt 放入本目录。
- 改动源代码、配置或数据后重新运行 `python verify.py`，并更新 `MANIFEST.csv` 与 `docs/data_discrepancies.md`。
- 冻结结果只读保存；新的实验输出写入外部临时目录。
