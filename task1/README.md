# CUMCM 2026 B 题问题 1

本目录给出问题 1 的紧凑实现：把每次 `±1°` 示向度写成两个半平面，求多观测可行凸多边形
\(P\)，再与半径 1800 m 的目标圆域精确相交，并计算最终区域 \(\Omega\) 的直径。

当前 Q1 的符号体系优先与 Q1 引用文献及本题几何推导保持一致；待 Q1/Q2/Q3 均稳定后，再统一全文符号和程序接口。

## 文件

- `solution.md`：可供论文正文改写的完整建模说明。
- `literature_mapping.md`：论文原结论、复用思想与本题新增推导的边界。
- `src/q1.py`：核心解析几何实现。
- `demo/`：四张论文风格示意图的生成脚本。
- `figures/`：PNG 与 PDF 图件。
- `tests/test_q1.py`：少量确定性验证。

## 运行

在仓库根目录执行：

```powershell
pytest task1/tests/test_q1.py -q
python task1/demo/demo_single_wedge.py
python task1/demo/demo_multi_intersection.py
python task1/demo/demo_circle_clipping.py
python task1/demo/demo_hexagon_counterexample.py
```

核心模块仅使用 Python 标准库；demo 使用仓库已有的 Matplotlib，不新增依赖。
