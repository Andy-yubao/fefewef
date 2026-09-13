# Q2 四策略正式实验数据

本目录中的数据由提交版 task2 重新生成，已删除 Expected Diameter（ED）。

配置：

- 随机种子：`20260911`
- 基础场景：400
- 每个基础场景重复：25
- 四种策略：`gdop_mean`、`geometry`、`fim_e`、`random`
- 每种策略：10,000 条记录
- 总评价记录：40,000 条
- 网格：250 m → 100 m → 50 m
- 后验样本：80
- 误差节点：5

主要文件：

- `raw/evaluations.csv`：逐条评价数据；
- `raw/selected_points.csv`：逐场景策略选点数据；
- `raw/base_scenarios.csv`：共享基础场景；
- `raw/run_manifest.json`：配置、依赖、种子和运行信息；
- `tables/strategy_summary.csv`：主要汇总统计；
- `tables/pairwise_comparison.csv`：配对比较。

重新运行：

```bash
cd submission_release/task2
PYTHONPATH=. python -m experiments.run_all
```
