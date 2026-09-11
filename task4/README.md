# B 题问题 4：机器狗定位与清除

## 当前目标与核心理解

本目录提供 T4 的可执行机器狗、统一 API 客户端、几何定位、策略和批量实验工具；本地评测机位于 `experiments/t4_local/`。策略只看到官方四个接口返回的信息，本地环境真值只在实验结束后用于评分。

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
- `clear_probe`：当前推荐；在 `integrated_route` 上复用清除位置探测其他频道，替代400 m内最多两个覆盖点，并从接收机当前频道开始交替扫描。

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
│   ├── clear_probe.py        # 清除点复用（当前推荐）
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
python3 -m task4.cli run --mode local --strategy clear_probe --seed 42 --output task4/outputs/seed42.json
```

连接独立本地 HTTP 服务测试完整链路：

```bash
python3 -m task4.cli run --mode local --server http://127.0.0.1:2027 \
  --robot-id local-robot --strategy clear_probe --output task4/outputs/http-seed42.json
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
python3 -m task4.cli run --mode remote --strategy clear_probe \
  --server http://127.0.0.1:2026 --robot-id '<实际参赛队号>' \
  --confirm-remote I_UNDERSTAND_THIS_USES_AN_OFFICIAL_TEST \
  --output task4/outputs/official-run.json
```

正式运行不会读取本地真值。网络故障时客户端用相同请求体和 `request_id` 重试同一动作。

单次输出文件包含完整请求/响应动作日志；一次 600 动作的本地 HTTP 测试约 260 KB，低于官方加密日志 2 MB 上限，但两者不是同一种日志，正式测试仍必须从官方模拟器导出原始加密日志。

## 关键参数

- `--grid-spacing`：仅旧方格策略使用，默认 600 m，小于 `1000/sqrt(2)`。
- `--grid-half-extent`：默认 1800 m；`[-1800,1800]^2` 完整包含目标圆。策略允许在圆外移动和检测，与题目一致。
- `--lattice-spacing`：新默认735 m，必须小于1000 m；联合规划下735 m优于旧760 m。
- `--replacement-distance`：`clear_probe` 默认400 m；450、550、600 m以上均在扩大实验中出现漏清。
- `--max-replaced-waypoints`：一次清除点最多替代的覆盖点，默认2。
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

最终默认策略还通过了独立本地 HTTP 端到端测试：seed 42 清除 15/15，466 个动作全部走 `/enter`、`/measure`、`/clear`、`/exit` HTTP 链路，虚拟时间 9245.44 s，与进程内运行一致。

另用固定随机选择种子 `2026091103` 从 `[0,1000000)` 抽取 seed `869462、379913、24546`，运行三次当前推荐策略。三例共清除 38/38 个源，总时间分别为 9185.02、9594.36、9956.30 s，首次清除分别为 770.47、714.69、701.54 s；路径图和逐例数据位于 `experiments/t4_analysis/outputs/random3/figures/`。该三例用于可视化与人工核查，不作为替代 1000 案例统计的新性能结论。

对最终 1000 案例的特征分析显示：总时间均值 10008.4 s、标准差 672.1 s、变异系数 6.72%；移动占虚拟时间 70.25%，移动距离与总时间相关系数为 0.856，是首要成本。无信号占测量约 90.33%；高定向源占比组比低占比组平均慢 592.7 s。完整分组、相关性和最慢案例表见 `experiments/t4_analysis/outputs/feature_analysis/feature_report.md`。

最新十轮迭代的完整证据见 `experiments/t4_analysis/outputs/iterations/ITERATION_REPORT.md`。当前默认和正式测试首选已更新为 `clear_probe / lattice-spacing=735 / replacement-distance=400 / max-replaced-waypoints=2`。在 seed 0–999 上1000/1000全清，平均9135.6 s、P95 10113.2 s、平均移动30670 m；独立 seed 1000–1999 同一位置/探测逻辑也1000/1000全清。相对旧 `opportunistic`，均值缩短8.72%、P95缩短7.68%、移动减少12.76%；相对更早的 `deferred` 均值缩短23.48%。

全定向500例和全向500例均全清，平均分别为10052.9 s和8257.5 s。更大的替代半径和提前终止可以把均值推进到约8.9 ks，但450/550/600/800 m替代及多组提前停止参数都出现漏清，因此没有选为默认。当前未达到8000 s目标，文档明确报告可靠配置的实际9135.6 s，不把漏清方案的虚假低耗时当作提升。

## 在线评测机实测

2026-09-11 已对案例 `YJVS-K983-5KCS-NAX5` 运行一次在线测试，使用当时的 `deferred / 600 / 1800`。671 个动作全部被接受；658 次检测，11 次清除均成功，最终虚拟时间 12529.850766 s。完整自记录日志为 `task4/outputs/official/YJVS-K983-5KCS-NAX5.json`。离线分析程序 `experiments/t4_analysis/analyze_action_log.py` 只读取机器人可见日志，得到 611 次无信号、49 个测量位置、首次清除动作 660、全部清除位于最后一次测量之后，以及 170 次无信号发生在最终确实被发现的频道上。分析产物位于 `experiments/t4_analysis/outputs/YJVS-K983-5KCS-NAX5-analysis.{json,md}`。

接口不会返回案例干扰源总数，因此仅凭 API 不能断言 11 个是否为该案例全部干扰源；需要人工查看模拟器测试结束页面中的总数/完成信息。本记录不是三次正式测试结果，也不能替代模拟器导出的官方加密日志。

## 已知问题与正式测试前检查

- 官方案例生成分布未知；本地数量/位置/半径/类型/误差分布只是明确记录的实验假设。现有一次在线测试不足以代替多次官方演练。
- 本地服务已覆盖主要字段、状态、错误码、幂等、重复 JSON 键、嵌套深度、Content-Type/Encoding、虚拟/现实超时规则；尚未完全模拟官方的并发新动作 409、429 流量保护、25 分钟界面窗口和连接直接关闭行为。
- `belief` 的粒子先验采用本地假设（位置面积均匀、半径均匀、定向概率 0.5）；覆盖格仍是可靠性兜底，所以先验错配主要影响效率，但尚无新在线案例验证这一点。
- 735 m三角格本身保留覆盖保证，但用清除探测点替代400 m内格点是经验启发式，不具备原三角格的严格最坏情况证明；目前证据是两个独立1000案例集合及两组500压力集零失败。
- 正式测试前人工核对：官方界面必须选“问题 4”；参赛队号、案例码和端口正确；先运行 `config-check`；最好先做一次不消耗正式次数的官方演练；确认策略为 `clear_probe`，参数为 `735 / 400 / 2`；确认输出目录可写；倒计时结束后才运行带确认串的命令；结束后立即导出官方加密日志。不要把旧在线日志的11次成功自动解释为该案例全部源，必须看GUI完成状态。
