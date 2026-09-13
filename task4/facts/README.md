# Q4 事实库（论文入口）

更新日期：2026-09-13（Asia/Shanghai）

## 当前最终选型

论文采用 `adaptive_double_ring_clear_probe`。它是一个独立注册的最终双环策略：25点发现覆盖不替代、50 m认证光学覆盖、清除点至多补测2个活跃频道、发现满16个频道后转入已知源可靠收尾。

请将三种容易混淆的口径分开：

1. `adaptive_double_ring_clear_probe` 是论文的最终算法及本地分层验证对象；
2. `geometry_early_optical_clear_probe / 731 / 550 / 2 / 35m / 100m` 是历史命令行默认/风险容忍方案，存在本地漏清，不能替代最终模型表述；
3. `results/q3_q4_formal_test_scores.md` 是正式三局的如实行为日志统计，日志未记录策略ID或案例真实源数，不能反推全清率或与本地批量数据混用。

阅读顺序：`current_model.md`（模型与证书）、`performance.md`（数字与边界）、`history.md`（模型去留），最后查本文件的证据索引。

## 论文可陈述的结论

- 25点双环发现覆盖与已见源的保守重捕获/光学条带收尾构成可靠性层；50m中心加十环点光学覆盖、有限清除点补测和路线重排构成效率层。
- 参数锁定后的5组本地验证共1000例，候选均全清；混合300例平均时间由6641.99降至6377.34 s，固定16源200例由6337.99降至5742.93 s。
- 固定16源组中，6000s内全清率从36.0%升至62.5%；这不等于每例都能在6000s内完成。

## 论文不得越界

- 本地生成分布、固定种子和配对对照不等于官方隐藏分布或正式成绩；不能声称全局最优、最坏情形6000s保证，或所有场景均更快。
- 50m光学环的覆盖证明只覆盖“已知可行域完全落入半径50m圆”的局部清除，不是整题完成时间上界。
- 不可因单次 `no_signal` 宣称频道不存在；对定向源，它还可能表示处于反向半平面或超出接收范围。

## 权威证据索引

- `experiments/t4_analysis/outputs/toward6000_v2/REPORT.md`：参数冻结、5组验证、退化案例、复现命令与证据边界；
- `results/task4_mixed100_vs_directional100/`：混合100与全定向100的自包含开发集复制件；
- `results/HANDOFF.md`：上述复制件和Q3并发规模测试的来源及复制边界；
- `experiments/t4_analysis/outputs/toward6000_v2/*/comparison.md`：各分层的配对明细；
- `task4/strategies/adaptive_double_ring_clear_probe.py`：最终实现；
- `results/q3_q4_formal_test_scores.md`：Q3/Q4正式三局统一台账；
- `task4/HANDOFF.md`：题设接口、物理参数和历史策略的工程交接。

## 最小复现

```powershell
python3 -m unittest discover -s task4/tests -v

python3 -B -m experiments.t4_analysis.optimize_double_ring `
  --strategy adaptive_double_ring_clear_probe `
  --strategy-config '{"early_clear_radius_m":50}' `
  --seed-start 10000 --cases 300 --workers 4 `
  --directional-probability 0.5 `
  --output-dir experiments/t4_analysis/outputs/toward6000_v2/reproduce_mixed300
```

封存时测试为49/49通过。批量命令须使用新输出目录，工具拒绝覆盖既有结果。
