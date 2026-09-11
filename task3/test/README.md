# 七点覆盖绘图与验证

本目录用解析计算、自动化测试和两幅图共同验证：原点加半径 1200 m 的正六边形顶点，其 7 个半径 1000 m 的必接收圆完全覆盖半径 1800 m 的目标圆域。

运行环境复用 `task2/.venv`：

```bash
task2/.venv/bin/python -m pytest task3/test/test_coverage_geometry.py -q
task2/.venv/bin/python task3/test/plot_coverage_disks.py
task2/.venv/bin/python task3/test/plot_coverage_margin.py
```

默认输出：

- `output/seven_point_disks.png`：目标圆、7 个必接收圆、固定搜索骨架和最坏边界点；
- `output/seven_point_margin.png`：全域最近检测点距离热力图，以及目标边界上的距离曲线。

解析最坏距离为 968.9016 m，小于 1000 m，最小覆盖裕量约 31.0984 m。密集采样只用于交叉检查，严格结论来自 `coverage_geometry.py` 中的六重对称解析界。
