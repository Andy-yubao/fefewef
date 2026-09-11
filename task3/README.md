# CUMCM B 题问题 3：自动搜索、定位与清除

本目录实现一只机器狗对未知数量全向干扰源的自动搜索、定位和清除。整体方法是“确定性保证层 + 时间优化层”：七点覆盖、分频道硬可行集、最小包围圆（MEC）清除证书和有限圆盘覆盖负责最终必发现、必清除；滚动调度、局部测点排序和顺路清除负责缩短虚拟时间。

概率粒子只参与动作排序，不会删除硬可行位置、生成清除证书或决定任务完成。程序不宣称全局最短时间。

## 1. 快速开始

推荐 Python 3.11。问题 3 的依赖单独维护在 `task3/requirements.txt`：

```bash
python3 -m venv task3/.venv
task3/.venv/bin/python -m pip install -r task3/requirements.txt
```

仓库现有的 `task2/.venv` 也可复用：

```bash
task2/.venv/bin/python -m pytest task3/test -q
```

当前回归结果为 31 项测试全部通过。

## 2. 代码是否按职责拆分

HTTP、几何、状态和策略已经分开编写，真实模拟器与离线 Mock 共用同一个控制器：

```text
experiments/run_practice.py
          |
          v
      src/main.py
          |
          v
  src/controller.py --------------------+
      |          |          |           |
      v          v          v           v
 client.py  scheduler.py  channel_state.py  coverage.py
                 |             |
                 v             v
          local_planner.py  geometry.py
```

各文件职责如下：

- `src/client.py`：`/enter`、`/measure`、`/clear`、`/exit`，串行请求、幂等重试、响应校验、虚拟时间、现实截止和脱敏日志；
- `src/geometry.py`：硬集合方格外包、角度和距离约束、MEC、安全清除证书及 20 m 圆盘兜底覆盖；
- `src/coverage.py`：原点加半径 1200 m 正六边形六顶点、解析覆盖证书、旋转方向和访问顺序；
- `src/channel_state.py`：20 个频道的状态机、观测历史、硬集合更新、兜底状态和终止判据；
- `src/local_planner.py`：局部候选测点生成以及 Geometry、E-optimal、expected-diameter、shortlist 排序；
- `src/scheduler.py`：在 `SEARCH`、`LOCALIZE`、`CLEAR` 中滚动选择下一动作；
- `src/controller.py`：把客户端、状态机和调度器连接成完整执行循环，并统计时间；
- `src/config.py`：题面物理参数、规划参数和客户端参数；
- `src/main.py`：通用命令行入口；
- `src/mock_simulator.py`：与真实客户端具有相同控制接口的离线随机模拟器。

一次真实运行的调用流程是：`run_practice.py -> main.py -> SimulatorClient + SearchController`。控制器先在原点扫描，再循环调用调度器，执行 HTTP 动作，更新对应频道的硬状态，满足严格终止条件后调用 `/exit`。

## 3. 确定性保证如何实现

每个频道独立维护：

```text
unknown -> found -> cleared
unknown -> absent
```

硬可行集使用边长 20 m 的闭方格单元并集作为连续真值集合的外包。只有能够证明整个方格不可能包含真值时才删除该格：

- `direction`：使用示向角两侧各 1°、最大接收距离 1500 m、正常示向距离大于 5 m 及目标圆域；
- `no_signal`：只删除测点周围半径 1000 m 的必接收圆；
- `near`：立即在当前位置清除；
- 同一频道同一位置不重复测量。

安全 MEC 对所有保留方格的四角计算并复核。只有外包 MEC 半径不超过 `20 - 0.25 = 19.75 m` 时，圆心才是认证清除点。若定位长期不能产生证书，则访问保留方格中心形成的有限覆盖；方格半对角线约 14.142 m，小于清除半径 20 m，因此单元内部没有覆盖缝隙。

正常终止只有两种：

1. 已成功清除题设上界 16 个目标；
2. 七点扫描全部完成，其余未知频道均有不存在证书，且所有发现频道均已清除。

覆盖完成后若清除数少于题设下界 10，程序报告异常，不把该局计为成功。

## 4. B3 和 Geometry 在哪里实现

策略由两个参数组成，而不是单个类：

```text
mode          全局调度方式
local_family  局部测点选择方式
```

B3 的配置为：

```text
mode=hybrid
local_family=shortlist
```

其中 `scheduler.py` 的 `hybrid` 分支开启粒子排序，`local_planner.py` 的 `_predicted_radii()` 估计期望定位半径、P90 半径和无信号风险，`select_by_family(..., "shortlist")` 按预计完成代价复排。粒子不改变硬状态。

Geometry 的配置为：

```text
mode=hybrid
local_family=geometry
```

`local_planner.py` 的 `_geometry_quality()` 评价候选点与已有视线的交角及距离条件，`select_by_family(..., "geometry")` 选取几何质量最高、移动代价不过大的点。七点覆盖、硬状态、MEC 和兜底逻辑与 B3 完全相同。

## 5. 已实现和验证的策略

全局模式可取：

```text
two_stage
enroute
rolling_hard
hybrid
```

局部选点可取：

```text
geometry
e_optimal
expected_diameter
shortlist
```

离线实验实际验证的命名组合为：

| 实验名 | `mode` | `local_family` | 含义 |
|---|---|---|---|
| `B0_two_stage` | `two_stage` | `shortlist` | 完成固定扫描后逐源处理 |
| `B1_enroute` | `enroute` | `shortlist` | 固定骨架加顺路清除 |
| `B2_rolling_hard` | `rolling_hard` | `shortlist` | 不使用概率粒子的硬滚动 |
| `B3_hybrid` | `hybrid` | `shortlist` | 硬保证加粒子排序 |
| `A_geometry` | `hybrid` | `geometry` | 几何交角选点 |
| `A_e_optimal` | `hybrid` | `e_optimal` | E-optimal 选点 |
| `A_expected_diameter` | `hybrid` | `expected_diameter` | 预计直径选点 |

程序入口目前需要指定 `mode` 和 `local_family`，不能直接写 `--policy A_geometry`。所有合法组合在代码层面可以构造，但只有上表组合及局部动作阈值 1/3/5 做过批量实验，不应把未测试的笛卡尔积组合描述成已验证策略。

## 6. 离线测试和随机实验

运行全部单元测试及七点覆盖证明：

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python -m pytest task3/test -q

task2/.venv/bin/python -m task3.experiments.export_coverage_certificate \
  --output-dir task3/results/tables
```

运行固定种子、配对场景的随机实验：

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python -m task3.experiments.run_offline \
  --cases 100 --workers 4 --seed 20260911 \
  --output task3/results/raw/offline_runs.jsonl.gz

MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python -m task3.experiments.analyze_results \
  --input task3/results/raw/offline_runs.jsonl.gz \
  --tables task3/results/tables --figures task3/results/figures \
  --bootstrap 2000 --seed 20260911

task2/.venv/bin/python -m task3.experiments.make_manifest \
  --output task3/results/raw/offline_manifest.json
```

离线 Mock 随机生成 10--16 个频道互异的全向源、1000--1500 m 接收半径和有界示向误差。同一频道同一位置的误差固定，不会把重复测量错误地当成独立样本。

100 个配对场景、9 个配置共 900 次运行均实现 100% 清除。平均虚拟时间如下：

| 策略 | 平均虚拟时间 |
|---|---:|
| B0 two-stage | 6110.3 s |
| B1 enroute | 5396.3 s |
| B2 rolling-hard | 5441.7 s |
| B3 hybrid-shortlist | 5463.8 s |
| Geometry | **4973.8 s** |
| E-optimal | 5511.0 s |
| Expected-diameter | 5792.6 s |

Geometry 是这批离线案例中最快的已测试策略，但这不是任意场景全局最优的证明。

## 7. Windows 模拟器与 WSL 演练

模拟器运行在 Windows、算法运行在 WSL 时，先确保 Windows 端口可从 WSL 访问。服务地址必须作为当次参数传入，不要写进源码、Git 配置或提交的 `.env`。可先检查：

```bash
nc -vz '<Windows 可达地址>' '<模拟器端口>'
```

然后在 Windows GUI 中：

1. 登录当前队号；
2. 明确选择“问题 3 演练测试”；
3. 启动一局并等待接口就绪；
4. 记录 GUI 显示的新案例编码；
5. 在 WSL 运行下列命令。

B3 演练：

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<当前登录参赛队号>' \
  --base-url 'http://<Windows 可达地址>:<端口>' \
  --case-id '<本局案例编码>' \
  --mode hybrid \
  --local-family shortlist \
  --local-action-limit 3
```

Geometry 演练：

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<当前登录参赛队号>' \
  --base-url 'http://<Windows 可达地址>:<端口>' \
  --case-id '<本局案例编码>' \
  --mode hybrid \
  --local-family geometry \
  --local-action-limit 3
```

每局应使用 GUI 新生成的案例编码。演练入口会把实际 `mode`、`local_family` 和局部动作上限写入 summary。队号在请求日志及 summary 中脱敏，不应提交机器专用地址或凭据。

GUI 显示真实目标数后，为该局补充分母并重新聚合：

```bash
task2/.venv/bin/python -m task3.experiments.annotate_practice \
  --summary task3/results/raw/practice/<案例-时间>.summary.json \
  --total '<GUI 真实目标数>'

task2/.venv/bin/python -m task3.experiments.analyze_practice \
  --input-dir task3/results/raw/practice \
  --output task3/results/tables/practice_summary.csv
```

异常时，程序仍保存此前已经接受的响应和错误 summary，并尝试安全 `/exit`。

## 8. 当前在线演练结果

已完成两次问题 3 演练：

| 案例 | 策略 | 目标/清除 | 清除率 | 总虚拟时间 | 平均时间 | 墙钟时间 | 清除落空 |
|---|---|---:|---:|---:|---:|---:|---:|
| `J2TJ-2H73-YG5X-Y4AZ` | B3 hybrid-shortlist | 16/16 | 100% | 5903.926 s | 368.995 s/个 | 2.910 s | 13 |
| `WBBE-W933-ZBEX-DQ7B` | hybrid-geometry | 12/12 | 100% | 4287.436 s | 357.286 s/个 | 1.867 s | 0 |

两局都完成 7/7 覆盖且无网络重试。Geometry 局的平均时间比 B3 局低 11.709 s/个，移动时间由 292.558 s/个降至 267.120 s/个；但两局目标配置不同，这只是积极线索，不是同案例配对实验。

主要结果位置：

- `results/raw/offline_runs.jsonl.gz`：离线逐案例原始记录；
- `results/raw/offline_manifest.json`：离线产物哈希与版本；
- `results/raw/practice/`：在线演练脱敏 JSONL 和 summary；
- `results/tables/offline_strategy_summary.csv`：策略汇总；
- `results/tables/offline_paired_vs_two_stage.csv`：配对比较；
- `results/tables/practice_summary.csv`：演练聚合；
- `results/figures/`：离线箱线图和经验分布图；
- `report/problem3_report_katex.md`：论文材料。

## 9. 当前性能瓶颈与优化方向

首轮 B3 的虚拟时间中移动占 79.28%，并发生 13 次兜底清除落空。Geometry 消除了该局中的清除落空，并减少单位目标移动时间，但检测时间有所增加。

当前最值得继续验证的方向是：

1. 增加 Geometry 在线演练样本，不能只凭两个不同案例定策略；
2. 把“6 次示向后兜底”改成“追加示向成本与有限覆盖成本”的自适应比较；
3. 覆盖点不再无条件测量所有已发现频道，只保留高几何收益的顺路观测；
4. 将候选测点、清除点和多频道路线联合排序，减少最近三个频道的局部贪心；
5. 保持七点覆盖、硬集合、MEC 清除和有限覆盖不变，以免用性能优化破坏正确性。

## 10. 正式测试保护

仓库故意不提供自动启动正式测试的脚本。正式测试只有三次机会，必须在用户当前明确授权后才可执行；测试前还须冻结代码和参数，并原样保存模拟器导出的加密日志。普通演练授权不等于正式测试授权。

`task3/prompt.md` 是用户输入文件，不属于实现成果；不要修改、移动或删除。
