# 提交版交接记录

本文档记录当前 `submission_release` 的维护状态、复现方法和交接事项。它不属于项目正文介绍。

## 当前状态

- 本目录是独立提交包，已不再依赖原代码库中的 `code/` 目录。
- Q2 已删除论文未采用的 ED 策略；正式实验和汇总表只保留 GDOP Mean、Geometry、FIM E、Random。
- Q2 的冻结原始数据、汇总表和运行清单来自同一批次，`GDOP Mean` 均值为 `52.377347 m`。
- 纸质代码附录由 `paper_appendix_sources.txt` 指定的源文件生成，只保留论文所需的核心策略实现。
- 四个问题的正式代码和冻结结果由 `verify.py` 统一核验。
- Q3、Q4 敏感性分析已补入 `results/task3_sensitivity_analysis/`、`results/task4_sensitivity_analysis/`；Q4 分析所依赖的混合/全定向源数据在 `results/task4_mixed100_vs_directional100/`。

## 独立复现

在本目录根部执行：

```bash
python -m pip install -r requirements.txt
python verify.py
```

运行完整测试：

```bash
python verify.py --tests
```

生成纸质代码附录：

```bash
python make_paper_appendix.py
```

Q4 小规模在线模拟：

```bash
python -m task4.cli run --mode local \
  --strategy adaptive_double_ring_clear_probe \
  --seed 42 --output /tmp/submission-q4-seed42.json
```

Q2/Q3/Q4 的完整实验入口分别位于 `task2/experiments/`、`task3/experiments/` 和 `task4/cli.py`。完整重跑会产生新的结果，不应直接覆盖冻结快照。

敏感性分析的归档分析脚本位于两个 `results/*_sensitivity_analysis/scripts/` 目录。Q3 的既有数据分析和 Q4 的既有数据分析可直接运行；Q4 的受控实验脚本可另指定输出目录，不应覆盖归档结果。

## 已完成的验证

最近一次发布版检查通过：

```text
PASS: Q1/Q2/Q3/Q4 formal-code and frozen-result checks
Q2 GDOP Mean: 52.377347 m
```

Q2 测试集为 13 项，全部通过。Q2 正式实验配置、随机种子和输出位置记录在 `task2/results/raw/run_manifest.json`；逐条结果在 `task2/results/raw/evaluations.csv`。

## 维护规则

- 只维护本目录中的正式源代码、配置和冻结数据。
- 纸质附录从本目录源文件导出，不单独维护第二份代码。
- 不把虚拟环境、缓存、历史候选策略或临时 prompt 放入本目录。
- 修改源代码、配置或数据后，重新运行 `python verify.py`，并同步检查 `MANIFEST.csv`。
- 冻结结果只读保存；新的实验输出写入外部临时目录。
