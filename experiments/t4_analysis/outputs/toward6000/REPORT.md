# Task4 双环光学策略实验报告

日期：2026-09-12。策略：`double_ring_optical_clear_probe`。所有结果来自进程内本地模拟器，没有调用官方接口。

## 实现配置

- 25 点双环覆盖：原点、980 m 内环 12 点、外接目标圆的外环 12 点。
- 默认不替代覆盖点：`max_replaced_waypoints=0`。
- 保留 35 m 提前光学；中心失败后用半径 22 m 正六边形完成七圆覆盖。
- 常规无线重捕获失败后，先查 100 m 近端中心线，再以两排光学点覆盖首条正示向的完整 1500 m、±1.01° 扇区。
- 保留原 100 m 路长余量内的示向几何排序。

## 测试结果

| 数据集 | 全清 | 均值/s | P95/s | 最大/s | 均移动/m | 均测量 | 全清且≤6000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 固定 seed 0–99 | 100/100 | 6735.71 | 7792.29 | 8627.22 | 24125.64 | 310.80 | 6/100 |
| 固定 seed 1000–1099 | 100/100 | 6665.87 | 8162.35 | 8456.60 | 23852.43 | 307.52 | 7/100 |
| 固定全定向 seed 3000–3099 | 100/100 | 7483.22 | 8788.43 | 9495.59 | 26830.14 | 345.56 | 0/100 |
| 固定全向 seed 3000–3099 | 100/100 | 5814.75 | 6219.71 | 6546.76 | 20746.64 | 269.66 | 71/100 |
| 新 OS 随机混合 | 1000/1000 | **6622.84** | **7716.41** | 9518.23 | 23762.91 | 303.86 | 106/1000 |
| 新 OS 随机全定向 | 300/300 | **7486.88** | **8891.01** | 11729.80 | 26885.50 | 344.08 | 1/300 |

分位数采用批量工具的 `(n-1)q` 线性插值。新随机混合和全定向的零失败单侧 95% 二项上界分别约为 0.299% 和 0.994%，仅适用于本地生成分布。

固定 seed 0–99 的当前默认 `geometry_early_optical_clear_probe / 731 / 550 / 2 / 35 / 100` 为 100/100，均值 7938.70 s、P95 8997.09 s。双环候选同种子均值节省 1202.99 s，93 例更快、7 例更慢。由于新随机 1000 与历史默认大样本不共享种子，`6622.84` 与历史 `7878.29` 的差值只能描述结果量级，不能当作配对因果估计。

## 可靠性诊断

开发中，只有 100 m 近端光学前缀时，独立混合 seed 1007、1070 和全定向 seed 3010 仍会留下已发现的定向源。加入完整示向条带覆盖后，三例均全清；历史回归 `12、257、918、3917738334、3880268419、289203195、62417761、2581748167、639107002` 也全部通过。

完整光学条带是尾部保障，不是常规动作。新随机混合 1000 中，81 例光学尝试超过 20 次，最大 116 次；全定向 300 中为 19 例，最大 44 次。这解释了全定向最大时间 11729.80 s。发现覆盖和最终清除具有构造性保障的前提是：保留全部 25 个覆盖点、官方规则与题目一致、数值/API 动作正常执行。

## 复现命令

```bash
python3 -m unittest discover -s task4/tests -v

python3 -m task4.cli batch \
  --strategy double_ring_optical_clear_probe --seed-start 0 --cases 100 \
  --max-replaced-waypoints 0 \
  --output-dir experiments/t4_analysis/outputs/toward6000/v2/double_ring_no_replace_0_99

python3 -m experiments.t4_analysis.random_benchmark \
  --cases 1000 --strategy double_ring_optical_clear_probe \
  --replacement-distance 550 --max-replaced-waypoints 0 \
  --early-clear-radius 35 --route-length-slack 100 \
  --output-dir experiments/t4_analysis/outputs/toward6000/final_random1000

python3 -m experiments.t4_analysis.random_benchmark \
  --cases 300 --strategy double_ring_optical_clear_probe \
  --replacement-distance 550 --max-replaced-waypoints 0 \
  --early-clear-radius 35 --route-length-slack 100 \
  --directional-probability 1 \
  --output-dir experiments/t4_analysis/outputs/toward6000/final_directional300
```

随机种子清单已在各输出目录的 `selected_seeds.json` 中先于运行保存。
