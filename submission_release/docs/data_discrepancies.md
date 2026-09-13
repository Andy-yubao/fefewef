# 数据与论文不一致记录

## Q2：已通过重跑统一

此前的 `evaluations.csv` 含有 ED，且论文表格与当前数据批次不一致。已删除 ED 实现和 ED 专用实验脚本，并按同一随机种子重新运行四种论文策略；当前 `evaluations.csv` 包含四种策略各 10,000 条记录。

| 策略 | 当前代码均值/m | 论文快照均值/m |
|---|---:|---:|
| GDOP Mean | 52.377347 | 52.377347 |
| Geometry | 67.666383 | 67.670000（论文保留值） |
| FIM E-optimal | 193.410880 | 193.410000（论文保留值） |
| Random | 588.035596 | 588.040000（论文保留值） |

当前发布版的原始数据和汇总表已经来自同一批次；正式提交前仍应重新生成论文图表并运行 `verify.py`。

## Q4：迁移校验

Q4 采用 `baseline/` 与 `candidate/` 两个目录。`baseline` 的策略名应为 `double_ring_optical_clear_probe`，`candidate` 的策略名应为 `adaptive_double_ring_clear_probe`。发布包已对这两类文件逐一复制并检查均值；如果策略名发生改变，说明迁移或数据选择出现错误。
