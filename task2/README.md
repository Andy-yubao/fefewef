# B 题问题 2：第二检测点选择

本目录是独立、可复现的交付单元；`src/` 不依赖 `tests/` 或
`experiments/`。正式结果使用固定种子 `20260911`，由 400 个基础几何状态、
每个状态 25 次第二观测组成，共 10,000 个有效观测场景和 100,000 条策略评价。

## 运行

```bash
python3 -m venv task2/.venv
task2/.venv/bin/python -m pip install -r task2/requirements.txt
PYTHONPATH=task2 task2/.venv/bin/python -m pytest -q task2/tests
MPLCONFIGDIR=/tmp/task2-mpl PYTHONPATH=task2 \
  task2/.venv/bin/python -m experiments.run_all
```

只做小规模链路检查：

```bash
PYTHONPATH=task2 task2/.venv/bin/python -m experiments.run_benchmark \
  --base-scenarios 12 --replicates 3 --quick
```

注意：小规模命令会覆盖 `results/raw/`，如需恢复正式结果，重新运行
`experiments.run_all`。

## 目录

- `src/geometry/`：扇区、目标可行域、候选域、面积与直径；
- `src/localization/`：观测事件、FIM、GDOP 与线性化误差代理；
- `src/strategies/`：十种选点策略；
- `tests/`：核心正确性与数值收敛测试；
- `experiments/`：场景生成、统一评测、统计和绘图；
- `results/raw/`：固定种子的原始场景、选点和逐条评价；
- `results/tables/`：汇总、成对比较、bootstrap CI、敏感性；
- `results/figures/`：论文图；
- `report/`：报告草稿、参考文献与数据字典。

## 复现约定

所有角度在程序内部使用弧度，输出图坐标和距离使用米。候选网格步长 250 m，
边界多边形分辨率 64，正式配置记录在 `results/raw/run_manifest.json`。

