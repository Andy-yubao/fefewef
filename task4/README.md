# B 题问题 4：机器狗定位与清除

## 当前目标与核心理解

本目录提供 T4 的可执行机器狗、统一 API 客户端、几何定位、策略和批量实验工具；本地评测机位于 `experiments/t4_local/`。策略只看到官方四个接口返回的信息，本地环境真值只在实验结束后用于评分。

当前风险容忍默认是 `geometry_early_optical_clear_probe / 731 / 550 / 2 / 35 m / 100 m`。新抽取的1000例混合集为999/1000全清，均值7878.29 s、P95 8836.33 s；1000例全定向集为998/1000全清，均值8674.85 s、P95 9792.46 s。两者案例失败率的单侧95%上界分别为0.4735%和0.6282%，均低于用户允许的1%。这是本地生成分布上的风险策略与统计证据，不是官方成绩或覆盖保证。

一次 `no_signal` 不能直接排除干扰源：它可能表示频道不存在、超过未知的 1000–1500 m 接收半径，或机器狗位于定向源 180° 发射半平面之外。因此当前实现采用“有几何保证的覆盖兜底 + 正信号硬扇区交会 + 正/负观测 belief + 定向失锁重捕获”。清除后立即退休频道；位置足够精确后进入 20 m 光学清除，不继续估计无关的发射方向。

对既有在线动作日志的独立复盘表明，旧 `deferred` 共测量 658 次，其中 611 次无信号（92.86%），第 660 个动作才首次清除，且 11 次清除全部发生在最后一次测量之后。这不是接口错误，而是“完整扫描后集中清除”的策略结构所致。新策略分别从覆盖点数、途中清除和搜索顺序三个层面修正这一问题。

## 文献方法如何落实

指定资料中的方法没有被原样搬用：Isler–Bajcsy 的 bounded-set 思路落实为“每次 ±1° 示向生成凸角扇区，多次观测取交”；Zhao–Chen–Lee 的近正交观测几何和 Dehghan 的候选航点滚动评价，落实为侧向/环绕候选点和交会角评分；Reynaud 的“已发现集合 + 未发现区域 + 正/负观测”落实为逐频道状态机、可见性粒子淘汰和覆盖兜底；Song 的结论用于约束负观测解释，禁止把单次未检出直接视为频道不存在。

`belief` 实现了轻量的 `(x,y,radius,type,direction)` 粒子模型：候选三角格点预计算粒子可见性位集；未发现频道在某点得到无信号后，淘汰从该点本应可见的粒子；下一点用二元熵近似信息增益、发现概率、已有示向的交会几何和移动代价联合排序。它不是完整 POMDP，也不读取本地真值。实验说明信息增益能明显减少无信号测量和提前首次清除，但若行程惩罚过低会因跨场跳跃而变慢，因此保留了经训练集/独立留出集验证的较高移动惩罚。

## 已实现策略

- `coverage`：固定 600 m 方格蛇形扫描，利用沿途自然获得的多次示向做 ±1.01° 硬扇区交会；这是可解释的 baseline。
- `active`：首次发现后立即选择改善交会几何的侧向/环形候选点；首次失锁即返回全局扫描。
- `reacquire`：在 `active` 基础上，失锁后继续尝试镜像侧移和局部绕行；作为定向失锁消融策略保留。
- `deferred`：旧推荐方案；600 m 方格近邻覆盖，频道定位后退休，最后集中清除，用于本轮改进的基准。
- `lattice`：以三角格代替方格，保留理想规则下的保证性覆盖。
- `opportunistic`：旧推荐；定位完成后按固定插入阈值途中清除。
- `belief`：粒子可见性 + 近似 EIG 航点排序 + 交会几何 + 途中清除。测量次数、无信号次数和首次清除时刻最优，但移动略多，平均总时间略逊于 `opportunistic`。
- `route_optimized`、`local_eig`、`rejoin_clear`：本轮保留的消融策略，分别测试固定2-opt回接、局部EIG、最优重入估价，均未超过最终方案。
- `early_stop`：概率性提前停止实验；速度更快但发生漏清，禁止作为正式默认。
- `integrated_route`：将未访问覆盖点和已定位清除点统一放入滚动开放TSP，避免清除后重复折返。
- `clear_probe`：上一轮推荐；在 `integrated_route` 上复用清除位置探测其他频道，替代400 m内最多两个覆盖点，并从接收机当前频道开始交替扫描。
- `clear_probe_multistart`：用多起点开放2-opt改进滚动联合路线。
- `certified_clear_probe`：仅在清除点与六个保留邻点可重建边长均小于1000 m的三角扇时替代格点；速度略慢，但替代具有局部覆盖证明。
- `active_clear_probe`、`endgame_clear_probe`、`optimized_clear_probe`：分别测试清除点 active 频道补测、残局频道排序及两者组合，作为尾部/消融策略保留。
- `replacement_aware_clear_probe`：第18轮推荐；规划时计入成功清除后将被替代的格点，使用无强制回头的多起点滚动开放路线，默认参数为731/400/2。
- `geometry_aware_clear_probe`：在近等长开放路线中用当前可见的示向交会几何打破平局；小样本更快，但 seed 257 漏清，禁止作为默认。
- `certified_geometry_clear_probe`：把上述示向几何排序限制在六邻点覆盖认证替代上；目前是通过回归与四组100例的待扩测认证候选。
- `early_optical_clear_probe`：证据更久的保守回退；在可行域半径30 m时提前安排光学尝试，失败后须估计中心移动至少5 m才重试。
- `ida_heuristic_clear_probe`：在提前光学上增加深度3的IDA*式 `g+h` 路线评价；均值更快但全定向随机测试漏清，禁止作为默认。
- `geometry_early_optical_clear_probe`：当前本地默认；将35 m提前光学与近等长路线的示向几何排序合并，仍只使用机器人可见信息。
- `guarded_ida_clear_probe`：只在满足首步几何门槛的路线内使用深度3 `g+h`；100%门槛可靠但总体略慢，作为消融保留。
- `relocate_geometry_clear_probe`：在开放2-opt后增加单点重插入局部搜索；静态路线更强但滚动总时间和程序墙钟时间均变差。
- `geometry_replacement_clear_probe`：在550 m候选中优先保留对 active 信道交会几何价值高的格点；300例仅快2.67 s且失败数未降，作为消融保留。

所有策略共享 HTTP、状态、计时、几何和清除逻辑。圆域与 1500 m 正信号距离约束使用外接正多边形，避免错误排除真值；示向误差额外留出 0.01° 以覆盖接口两位小数舍入。

## 文件结构

```text
task4/
├── README.md                 # 中文运行与算法文档
├── HANDOFF.md                # 英文工程交接
├── client.py                 # HTTP / 本地进程内统一四接口客户端
├── geometry.py               # 角度、扇区、凸多边形交、最小包围圆
├── search_patterns.py        # 方格之外的三角覆盖格点
├── strategies/               # 策略包：公共部分与具体策略分离
│   ├── base.py               # ChannelBelief、结果类型、公共动作封装
│   ├── coverage.py           # 固定扫描 baseline
│   ├── active.py             # 检出后立即主动定位
│   ├── reacquire.py          # 定向失锁重捕获扩展
│   ├── deferred.py           # 延迟集中清除基准及扩展钩子
│   ├── lattice.py            # 三角格覆盖
│   ├── opportunistic.py      # 途中机会清除旧方案
│   ├── belief.py             # 粒子可见性与近似信息增益排序
│   ├── route_optimized.py    # 固定2-opt回接消融
│   ├── local_eig.py          # 局部EIG消融
│   ├── rejoin_clear.py       # 清除后最优重入估价消融
│   ├── early_stop.py         # 有漏清风险的提前停止实验
│   ├── integrated_route.py   # 覆盖/清除节点联合滚动规划
│   ├── clear_probe.py        # 清除点复用（上一轮推荐）
│   ├── replacement_aware_clear_probe.py # 替代感知滚动路线
│   ├── certified_clear_probe.py # 有局部覆盖证明的保守替代
│   ├── geometry_aware_clear_probe.py # 近等长路线的示向几何排序实验
│   ├── certified_geometry_clear_probe.py # 覆盖认证 + 示向几何候选
│   ├── early_optical_clear_probe.py # 30 m提前光学（保守回退）
│   ├── ida_heuristic_clear_probe.py # IDA*式有界路线评价实验
│   ├── geometry_early_optical_clear_probe.py # 示向几何 + 35 m提前光学（当前默认）
│   ├── guarded_ida_clear_probe.py # 受首步几何门控的IDA*融合
│   ├── relocate_geometry_clear_probe.py # Or-opt-1路线消融
│   ├── geometry_replacement_clear_probe.py # 几何感知格点替代消融
│   ├── registry.py           # 策略注册表和 make_strategy
│   └── __init__.py           # 稳定的公共导入接口
├── cli.py                    # 单次、本地批量、远程安全入口
├── outputs/                  # 已实际运行的基准、压力测试与失败案例
└── tests/                    # 几何与模拟器规则测试
experiments/
├── t4_local/
│   ├── benchmark.py          # 固定种子批量实验、CSV/JSON/Markdown 汇总
│   ├── engine.py             # 环境生成、状态机、计时、统计和真值隔离
│   └── server.py             # 官方路径兼容的本地 HTTP 服务
└── t4_analysis/              # 与机器人代码隔离的离线实验研究
    ├── analyze_action_log.py # 在线可见动作日志诊断
    ├── compare_summaries.py  # 只读取持久化 summary.json 的公平比较
    ├── plot_action_logs.py   # 动作路径、探测点、清除点与本地真值 SVG
    ├── analyze_benchmark_features.py # 分布、分组、相关性和尾部特征
    ├── analyze_coverage_failure.py # 本地运行结束后的覆盖失效诊断
    ├── random_benchmark.py # 用操作系统熵选择不重复种子的随机大样本测试
    └── outputs/              # 调参、留出集、最终基准和压力测试结果
```

新增策略时，在 `task4/strategies/` 下新建一个独立模块，实现 `BaseStrategy.run()`，然后只在 `registry.py` 注册；不需要复制 HTTP、测量、清除、状态或几何代码。外部调用仍统一使用 `make_strategy(name)`。

## 安装与测试

仅使用 Python 3.10+ 标准库，无第三方依赖。在项目根目录执行：

```bash
python3 -m unittest discover -s task4/tests -v
```

## 启动本地服务

```bash
python3 -m experiments.t4_local.server --seed 42 --port 2027
```

服务路径与官方一致：`POST /enter`、`/measure`、`/clear`、`/exit`。服务结束时在终端打印环境真值和统计。当前本地生成假设为：数量均匀取 10–16，频道无放回抽取，位置在圆域内按面积均匀，接收半径均匀取 1000–1500 m，定向概率默认 0.5，定向方向均匀；这些是本地实验假设，不是官方未公开的生成分布。

## 单次本地测试

快速进程内测试（策略仍只经过四接口抽象）：

```bash
python3 -m task4.cli run --mode local --strategy geometry_early_optical_clear_probe \
  --seed 42 --output task4/outputs/seed42.json
```

连接独立本地 HTTP 服务测试完整链路：

```bash
python3 -m task4.cli run --mode local --server http://127.0.0.1:2027 \
  --robot-id local-robot --strategy geometry_early_optical_clear_probe \
  --output task4/outputs/http-seed42.json
```

若要验证真实 HTTP 链路，先启动上述服务，再用上面的 `--mode local --server ...` 形式连接；为防止误触官方次数，CLI 的 `remote` 模式有强制确认串，详见下节。

## 批量实验

```bash
python3 -m task4.cli batch --strategy coverage --seed-start 0 --cases 100 --output-dir task4/outputs/coverage_0_99
python3 -m task4.cli batch --strategy opportunistic --seed-start 0 --cases 100 --output-dir task4/outputs/opportunistic_0_99
```

公平 A/B 测试必须使用相同 `seed-start` 与 `cases`。输出：

- `cases.csv`：逐案例清除率、总虚拟时间、移动、检测、无信号率、切频、光学、首见/首次清除、首次清除前测量、失锁/重捕获和实际运行时间。
- `first_seen.csv`：每个真实干扰源的频道、类型和首次发现虚拟时刻；只用于本地实验分析。
- `summary.json` / `summary.md`：总体清除率、全清案例率、均值以及 P50/P90/P95/最大尾部时间。
- `failure_seed_N.json`：失败案例的真值与策略摘要，可用 `run --seed N` 重现。

离线研究工具与正式策略代码分开。复盘单次动作日志、比较已落盘批量汇总的示例：

```bash
python3 -m experiments.t4_analysis.analyze_action_log task4/outputs/official/YJVS-K983-5KCS-NAX5.json \
  --output-dir experiments/t4_analysis/outputs
python3 -m experiments.t4_analysis.compare_summaries \
  experiments/t4_analysis/outputs/final1000/deferred/summary.json \
  experiments/t4_analysis/outputs/final1000/lattice/summary.json \
  experiments/t4_analysis/outputs/final1000/opportunistic/summary.json \
  experiments/t4_analysis/outputs/final1000/belief/summary.json \
  --baseline-label deferred --output-dir experiments/t4_analysis/outputs/final1000/comparison
```

`compare_summaries.py` 只消费已保存的 JSON，不导入策略或模拟器内部状态；输出 `comparison.csv` 和可直接用于论文整理的 `comparison.md`。

对一个或多个本地单次运行日志绘制无需第三方库的 SVG 路径图：

```bash
python3 -m experiments.t4_analysis.plot_action_logs \
  experiments/t4_analysis/outputs/random3/seed_869462.json \
  experiments/t4_analysis/outputs/random3/seed_379913.json \
  experiments/t4_analysis/outputs/random3/seed_24546.json \
  --selection-seed 2026091103 \
  --output-dir experiments/t4_analysis/outputs/random3/figures
```

图中蓝线为动作位置序列，灰点为该位置全部未检出，橙点表示至少一次检出，绿色叉号及 `C顺序:频道` 表示成功清除；紫圆和红三角分别是本地全向/定向源真值，红色短线表示发射方向。真值仅在运行结束后绘图，不会进入策略。

## 官方模拟器测试与安全检查

先做不联网、不发送请求的配置检查：

```bash
python3 -m task4.cli config-check --server http://127.0.0.1:2026 --robot-id '<实际参赛队号>'
```

确认官方界面已经进入正确的“问题 4”测试、倒计时结束且接口就绪后，正式命令必须显式写出 `--mode remote` 和确认串：

```bash
python3 -m task4.cli run --mode remote --strategy early_optical_clear_probe \
  --server http://127.0.0.1:2026 --robot-id '<实际参赛队号>' \
  --confirm-remote I_UNDERSTAND_THIS_USES_AN_OFFICIAL_TEST \
  --output task4/outputs/official-run.json
```

正式运行不会读取本地真值。网络故障时客户端用相同请求体和 `request_id` 重试同一动作。

单次输出文件包含完整请求/响应动作日志；一次 600 动作的本地 HTTP 测试约 260 KB，低于官方加密日志 2 MB 上限，但两者不是同一种日志，正式测试仍必须从官方模拟器导出原始加密日志。

## 关键参数

- `--grid-spacing`：仅旧方格策略使用，默认 600 m，小于 `1000/sqrt(2)`。
- `--grid-half-extent`：默认 1800 m；`[-1800,1800]^2` 完整包含目标圆。策略允许在圆外移动和检测，与题目一致。
- `--lattice-spacing`：当前推荐策略默认731 m，其他新策略的 CLI 默认735 m；必须小于1000 m。731 m位于格点数从43降至37的拓扑阈值上方，并在主集与留出集验证。
- `--replacement-distance`：当前融合策略默认550 m，其他清除点替代策略默认400 m。550 m不是覆盖证明，而是经混合/全定向各1000例验证、失败率95%上界低于1%的风险设置。
- `--max-replaced-waypoints`：一次清除点最多替代的覆盖点，默认2。
- `--route-length-slack`：示向几何路线策略使用；当前融合默认允许在最短路线以上100 m内以当前示向交会几何选首点。60 m在定向回归案例漏清，120 m在配对随机100例略慢。
- `--early-clear-radius`：提前光学阈值；`geometry_early_optical_clear_probe` 默认35 m，其他提前光学策略默认30 m。40 m融合版虽未漏清，但均值和尾部更差；IDA*式40 m曾在 seed 257 漏清。
- `--clear-detour-threshold`：途中清除允许的路线插入代价，默认 1500 m；调参中 1500 m 的均值最好，3000 m 的 P95 略好，差异很小。
- `--particle-count`：`belief` 可见性粒子数，默认 1600；粒子只属于策略内部近似，不是环境真值。
- `--belief-travel-weight`：belief 航点评分的行程惩罚，默认 16。过低会为了信息增益频繁跨场移动。
- `--directional-probability`：仅批量本地实验使用；默认 0.5，可用 0 或 1 做全向/全定向压力测试。
- 定向源概率及生成分布仅属于本地评测机参数，不应写成题目已知事实。

## 已完成实验与当前推荐

下表全部是本地模拟结果，不是官方成绩。最终比较使用相同 seed 0–999、默认 50% 定向概率；四者均 1000/1000 全清：

| 策略 | 平均总时(s) | 相对旧基线 | P95(s) | 平均移动(m) | 平均测量 | 平均无信号 | 首次清除(s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deferred` | 11938.3 | 基线 | 12820.7 | 40812 | 618.8 | 567.4 | 10077.4 |
| `lattice` | 10619.4 | -11.05% | 11465.1 | 38201 | 486.0 | 440.1 | 8740.4 |
| `opportunistic` | **10008.4** | **-16.17%** | **10954.7** | **35157** | 485.7 | 440.0 | 1099.6 |
| `belief` | 10051.6 | -15.80% | 11160.8 | 36772 | **439.0** | **394.6** | **711.4** |

调参只使用 seed 0–99；随后在未参与调参的 seed 1000–1199 上验证：`opportunistic` 和 `belief` 都是 200/200 全清，相对 `deferred` 的平均总时间分别降低 16.05% 和 15.91%，说明提升没有在简单留出集上消失。完整调参、留出集和最终结果分别位于 `experiments/t4_analysis/outputs/*_sweep/`、`holdout200/`、`final1000/`。

压力测试使用 seed 2000–2499。`opportunistic` 在 500 个全定向和 500 个全向案例中均全清，平均总时间分别为 10682.0 s、9217.0 s；`belief` 同样均全清，分别为 10812.0 s、9192.5 s。结果在 `experiments/t4_analysis/outputs/stress500/`。

旧策略曾通过独立本地 HTTP 端到端测试。当前 `replacement_aware_clear_probe / 731 / 400 / 2` 也已完成同类测试：seed 42 清除15/15，435个动作全部走 `/enter`、`/measure`、`/clear`、`/exit` HTTP链路，虚拟时间8180.87 s，与进程内运行完全一致；客户端日志为 `experiments/t4_analysis/outputs/iteration18_http_seed42.json`。

另用固定随机选择种子 `2026091103` 从 `[0,1000000)` 抽取 seed `869462、379913、24546`，运行三次当时推荐的旧 `opportunistic` 策略。三例共清除 38/38 个源，总时间分别为 9185.02、9594.36、9956.30 s；路径图和逐例数据位于 `experiments/t4_analysis/outputs/random3/figures/`。这些图不是当前策略的视觉证据。

对最终 1000 案例的特征分析显示：总时间均值 10008.4 s、标准差 672.1 s、变异系数 6.72%；移动占虚拟时间 70.25%，移动距离与总时间相关系数为 0.856，是首要成本。无信号占测量约 90.33%；高定向源占比组比低占比组平均慢 592.7 s。完整分组、相关性和最慢案例表见 `experiments/t4_analysis/outputs/feature_analysis/feature_report.md`。

前十轮迭代把推荐推进到 `clear_probe / 735 / 400 / 2`：seed 0–999 上1000/1000全清，平均9135.59 s、P95 10113.22 s。第11–18轮的完整证据见 `experiments/t4_analysis/outputs/iterations/ITERATION_REPORT.md`。第18轮当时更新为 `replacement_aware_clear_probe / lattice-spacing=731 / replacement-distance=400 / max-replaced-waypoints=2`。它在 seed 0–999 上1000/1000全清，平均8919.61 s、P95 9911.17 s、平均移动29679 m；在独立 seed 1000–1999 上也1000/1000全清，平均8905.56 s、P95 9946.97 s。相对上一轮推荐，主集均值缩短2.36%、P95缩短2.00%。

新推荐在 seed 3000–3499 的全定向500例和全向500例中均全清，平均分别为9778.72 s和7876.72 s，P95分别为10800.13 s和8604.61 s。全向本地压力均值已低于8000 s，但混合主集仍为8919.61 s，因此总体目标尚未达到。更大的替代半径和提前终止虽可能更快，但450/550/600/800 m替代及多组提前停止参数都出现漏清，不选为默认。

已复现两个覆盖替代回归案例：旧激进配置在 seed 257（450 m）清除11/12、seed 918（550 m）清除15/16。离线脚本 `experiments/t4_analysis/analyze_coverage_failure.py` 表明，918是被删格点造成定向可见性空洞，257则是已发现频道缺少足够的定向交会几何。新推荐731/400/2分别清除12/12（8829.27 s）和16/16（8653.12 s）。该脚本只在运行结束后读本地真值，不被策略导入。

第19--21轮又测试了示向几何路线排序。未认证的 `geometry_aware_clear_probe / 731` 在两组混合100例上分别达到8723.56 s和8614.81 s，但 seed 257 仅清除11/12；把路线余量从0扫到80 m仍未修复，故拒绝。随后 `certified_geometry_clear_probe / 735` 将同一排序与六邻点覆盖认证组合：seed 257、918均全清；seed 0--99、1000--1099以及同一组100例全定向、全向压力测试全部全清，均值分别为8916.14、8757.53、9659.16、8058.58 s。它是值得扩大验证的覆盖认证候选，但批量证据只有400例，暂不替换已验证3000例的当前默认。总体混合均值8000 s目标仍未达到。

另对当前默认进行了一次不使用预设选择种子的随机1000例测试。`random_benchmark.py` 通过操作系统熵现场选择1000个互不重复的32位种子，并在运行前保存完整清单。实际结果为1000/1000全清：最少5527.82 s、均值8909.21 s、标准差611.80 s、中位数8908.40 s、P90/P95/P99为9622.82/9967.15/10467.40 s、最大11133.29 s。最快 seed `3581489261` 有16个源、5个定向源；最慢 seed `3266971321` 有11个源、6个定向源。清单、逐例CSV和汇总位于 `experiments/t4_analysis/outputs/random_large_1000_replacement_aware/`。

第22轮把当前默认更新为 `early_optical_clear_probe / 731 / 400 / 2 / 30m`。在上述同一随机1000例中仍为1000/1000全清，均值降至8353.66 s、P95 9290.72 s、最大10261.54 s；平均移动28040.92 m、测量452.33次、光学尝试13.531次。另在同种子全定向、全向各200例中全部全清，均值分别为9075.41 s和7535.33 s；seed 257、918均通过。30 m提前尝试节省了后续探测和移动，而不是只把5秒无线测量机械替换成3秒失败光学。

第23轮随机100例中，`certified_geometry_clear_probe / 735` 100/100全清、均值8744.85 s，是保留覆盖认证的备选，但慢于同批提前光学的8309.65 s。第24轮IDA*式深度3评价在随机300例达到8121.88 s且全清，却在全定向随机100例中于 seed `3917738334` 漏清1个定向源；第25轮把光学阈值放宽到40 m又使 seed 257 仅清除11/12。二者均已拒绝。当前可靠混合均值仍未低于8000 s。

第26轮把示向几何路线排序与30 m提前光学合并为 `geometry_early_optical_clear_probe`。在配对随机100例和300例中均全清，均值分别为8041.52 s和8123.04 s；同种子全定向、全向各100例也全部全清，均值8939.45 s和7348.36 s，且 seed 257、918、3917738334 均通过。第27轮只把光学阈值调到35 m：配对随机100例和300例仍全部全清，均值8027.42 s和8095.16 s；全定向、全向各100例均全清，均值8881.02 s和7259.03 s。随后由操作系统熵新抽取的混合1000例也是1000/1000全清，最少/均值/中位数/P95/P99/最大为4299.72/8133.23/8186.92/8982.90/9498.41/10731.29 s；零失败的单侧95%二项上界约0.299%。另一个新抽取的全定向300例为300/300全清，最少/均值/中位数/P95/最大为6552.27/8833.18/8799.38/9812.92/10727.76 s，对应上界约0.994%。这些概率界只适用于明确记录的本地生成分布。35 m/100 m现为当前本地默认，但混合均值仍未压到8000 s以下。

第28--31轮逐次只改一个因素。40 m在随机100例虽100/100全清，但均值/P95恶化到8100.66/9179.47 s；路线余量从100 m收紧到60 m，以及深度1的 `行程时间 - 几何信用` 评分，均在全定向 seed `3917738334` 漏清频道5，离线诊断发现两个被替代格点本可见；路线余量放宽到120 m则在随机100例均值8038.20 s，慢于100 m的8027.42 s。因此保留35 m/100 m候选。所有诊断只在本地运行完成后读取真值，未反馈给策略。

第32--33轮尝试融合 `g+h`：90%首步几何门槛仍在 seed `3917738334` 漏清；提高到100%后，回归、随机100/300及两组100例压力集均全清，但随机300均值8098.30 s，比当前8095.16 s慢3.14 s，因此保留为消融而不替换默认。第34轮在每条开放2-opt候选上增加Or-opt-1重插入，随机100例100/100全清但均值8046.19 s、程序墙钟约1.45 s/例，均差于当前候选。更短的单次静态路线会改变清除与格点替代顺序，不保证整个滚动过程更短。

第35轮只把当前策略的替代半径从400 m提高到450 m，以重新利用允许不超过1%漏清的风险预算。新的OS随机混合1000例为1000/1000全清，均值8048.58 s；全定向先测300例有1例失败，随后追加700例全清，合并为999/1000、均值8833.46 s、P95 9831.36 s，单侧95%失败率上界0.4735%，因此曾短暂提升为风险默认。

第36轮只把替代半径从450 m提高到550 m。同种子随机100/300均值为7821.07/7852.46 s，300例有1例失败；全定向/全向100例均全清，均值8794.30/6956.57 s。最终由操作系统熵独立抽取的混合1000例为999/1000，最少/均值/中位数/P95/P99/最大5252.97/7878.29/7910.04/8836.33/9343.67/9794.08 s，源级清除率99.9923%；独立全定向1000例为998/1000，最少/均值/中位数/P95/P99/最大6302.65/8674.85/8642.54/9792.46/10302.60/10891.37 s，源级清除率99.9846%。对应单侧95%案例失败率上界0.4735%和0.6282%，均低于1%，因此550 m成为当前风险容忍默认，并首次在大规模随机混合集中把均值压到8000 s以下。

第37轮只改变替代点排序：保护 active 信道几何价值高的候选点。它修复部分已知失败，但未修复 seed `3880268419` 和 `289203195`；同种子随机100/300均值7808.72/7849.79 s，300例仍为299/300，仅比默认快2.67 s。收益太小且失败数未降，不提升。所有失败诊断均在运行结束后由 `experiments/t4_analysis/` 读取本地真值，未反馈给策略。

## 在线评测机实测

2026-09-11 已对案例 `YJVS-K983-5KCS-NAX5` 运行一次在线测试，使用当时的 `deferred / 600 / 1800`。671 个动作全部被接受；658 次检测，11 次清除均成功，最终虚拟时间 12529.850766 s。完整自记录日志为 `task4/outputs/official/YJVS-K983-5KCS-NAX5.json`。离线分析程序 `experiments/t4_analysis/analyze_action_log.py` 只读取机器人可见日志，得到 611 次无信号、49 个测量位置、首次清除动作 660、全部清除位于最后一次测量之后，以及 170 次无信号发生在最终确实被发现的频道上。分析产物位于 `experiments/t4_analysis/outputs/YJVS-K983-5KCS-NAX5-analysis.{json,md}`。

接口不会返回案例干扰源总数，因此仅凭 API 不能断言 11 个是否为该案例全部干扰源；需要人工查看模拟器测试结束页面中的总数/完成信息。本记录不是三次正式测试结果，也不能替代模拟器导出的官方加密日志。

## 已知问题与正式测试前检查

- 官方案例生成分布未知；本地数量/位置/半径/类型/误差分布只是明确记录的实验假设。现有一次在线测试不足以代替多次官方演练。
- 本地服务已覆盖主要字段、状态、错误码、幂等、重复 JSON 键、嵌套深度、Content-Type/Encoding、虚拟/现实超时规则；尚未完全模拟官方的并发新动作 409、429 流量保护、25 分钟界面窗口和连接直接关闭行为。
- `belief` 的粒子先验采用本地假设（位置面积均匀、半径均匀、定向概率 0.5）；覆盖格仍是可靠性兜底，所以先验错配主要影响效率，但尚无新在线案例验证这一点。
- 731 m三角格本身保留覆盖保证，但清除点替代仍是经验启发式，不具备原三角格的严格最坏情况证明。400 m旧方案有两组1000例及两组500例零失败；当前550 m风险方案已有明确漏清，只是统计上满足允许的1%边界。若必须优先要替代证明，可用较慢的 `certified_clear_probe`。
- 未经新的明确授权不要运行正式在线测试。若以后获准，人工核对官方界面为“问题 4”、队号/案例码/端口、输出目录与倒计时；风险默认是 `geometry_early_optical_clear_probe / 731 / 550 / 2 / 35m / 100m`，零漏清偏好下可改用400 m或认证回退。结束后立即导出官方加密日志，并以GUI完成状态核对总数。

## 当前结果复现

```bash
python3 -m task4.cli batch --strategy replacement_aware_clear_probe \
  --seed-start 0 --cases 1000 --lattice-spacing 731 \
  --output-dir experiments/t4_analysis/outputs/iteration18_final1000/replacement_aware_s731
python3 -m task4.cli batch --strategy replacement_aware_clear_probe \
  --seed-start 1000 --cases 1000 --lattice-spacing 731 \
  --output-dir experiments/t4_analysis/outputs/iteration18_holdout1000/replacement_aware_s731
python3 -m task4.cli batch --strategy replacement_aware_clear_probe \
  --seed-start 3000 --cases 500 --directional-probability 1 --lattice-spacing 731 \
  --output-dir experiments/t4_analysis/outputs/iteration18_stress500/replacement_aware_s731_dir
python3 -m task4.cli batch --strategy replacement_aware_clear_probe \
  --seed-start 3000 --cases 500 --directional-probability 0 --lattice-spacing 731 \
  --output-dir experiments/t4_analysis/outputs/iteration18_stress500/replacement_aware_s731_omni
```
