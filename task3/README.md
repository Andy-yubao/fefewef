# CUMCM B 题问题 3：自动搜索、定位与清除

> **当前事实入口（2026-09-12）**：队内最终采用
> `candidate_041_dynamic_open_route_deferred_cross_view`。论文写作、性能引用和
> 策略说明以 [`task3/facts/README.md`](facts/README.md) 为唯一当前索引。
> 本文件后续章节保留早期阶段的使用说明与历史数据，其中“当前冠军”“默认策略”
> 等旧表述不再代表最终选型。

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

当前回归结果为 112 项测试全部通过。

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
route_geometry
multi_geometry
center_approach
centroid_approach
mec_approach
chebyshev_approach
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

策略注册表位于 `src/policies.py`。现在本地和在线演练入口都支持 `--policy <策略ID>`，会一次加载对应的全局模式、局部选点器和全部规划参数。例如稳定 Geometry 基线是 `champion_000_geometry_baseline`，实验性 5 m 网格中心接近策略是 `candidate_020_grid5_center_approach`。`--policy` 会覆盖手动填写的 `--mode` 和 `--local-family`；除非专门调试，不要混用两套选择方式。

所有注册策略在代码层面均可构造，但只有历史基线做过原来的100案例批量实验；固定16源优化候选多数仅完成 smoke/小样本探测，尚未满足稳定晋级标准。注册存在不等于性能已经验证。

## 6. 如何手动进行本地测试

以下命令都在仓库根目录执行，只使用本地 `MockSimulator`，不会访问网络。

### 6.1 检查环境和完整单元测试

先确认解释器和依赖可用：

```bash
task2/.venv/bin/python --version
task2/.venv/bin/python -c "import numpy, scipy, matplotlib; print('dependencies: OK')"
```

运行全部单元测试：

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python -m pytest task3/test -q
```

成功时应看到类似：

```text
33 passed
```

单独导出并检查七点覆盖证书：

```bash
task2/.venv/bin/python -m task3.experiments.export_coverage_certificate \
  --output-dir task3/results/tables
```

`coverage_certificate.csv` 中的 `valid` 必须为 `True`，`worst_distance_m` 必须小于 1000 m。

### 6.2 运行一个固定16源的本地案例

下面用种子316000运行一个固定含16个目标的稳定 Geometry 策略：

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python \
  -m task3.experiments.run_offline \
  --cases 1 \
  --workers 1 \
  --seed 316000 \
  --source-count 16 \
  --policies champion_000_geometry_baseline \
  --output task3/results/raw/optimization/manual_champion_seed316000.jsonl.gz
```

`--workers 1` 最适合手动排错；`--source-count 16` 明确固定目标数。相同种子、策略和配置重复运行时，逐案例虚拟时间和动作摘要应一致。

查看该案例的路线诊断：

```bash
task2/.venv/bin/python -m task3.experiments.inspect_routes \
  task3/results/raw/optimization/manual_champion_seed316000.jsonl.gz \
  --policy champion_000_geometry_baseline \
  --first 1
```

### 6.3 在同一随机案例上比较两个策略

必须在一条命令中给出多个策略，才能确保使用完全相同的目标位置、频道、接收半径和示向误差：

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python \
  -m task3.experiments.run_offline \
  --cases 20 \
  --workers 1 \
  --seed 316000 \
  --source-count 16 \
  --policies \
    champion_000_geometry_baseline \
    candidate_020_grid5_center_approach \
  --output task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz
```

分析均值、P90/P95、最大值、清除率和配对节省：

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python \
  -m task3.experiments.analyze_results \
  --input task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz \
  --tables task3/results/tables/manual_pair_020 \
  --figures task3/results/figures/manual_pair_020 \
  --bootstrap 2000 \
  --seed 20260911 \
  --baseline champion_000_geometry_baseline
```

重点检查生成的 `offline_strategy_summary.csv`：两个策略的 `full_clear_rate` 和 `coverage_complete_rate` 都必须为1。再检查 `offline_paired_vs_two_stage.csv` 中的配对均值、胜率和置信区间。文件名沿用历史名称，但此处基线由 `--baseline` 指定，不一定真是 two-stage。

### 6.4 如何查看 `.jsonl.gz` 原始结果

`.jsonl.gz` 是gzip压缩的JSON Lines文件：第一行是实验配置和策略元数据，后续每行是一个“案例×策略”的完整结果。不要直接用普通文本编辑器打开压缩文件。

快速查看原始内容（长行左右滚动）：

```bash
gzip -cd task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz | less -S
```

只查看第一行实验元数据：

```bash
gzip -cd task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz \
  | sed -n '1p' \
  | task2/.venv/bin/python -m json.tool \
  | less
```

在终端打印每个策略的案例数、16/16成功数和时间摘要：

```bash
task2/.venv/bin/python - <<'PY'
import gzip
import json
import statistics

path = "task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz"
with gzip.open(path, "rt", encoding="utf-8") as handle:
    metadata = json.loads(next(handle))
    rows = [json.loads(line) for line in handle]

print("metadata:", {
    "case_count": metadata["case_count"],
    "source_count": metadata["source_count"],
    "seed_start": metadata["paired_scenario_seed_start"],
    "policies": list(metadata["policies"]),
})

for policy in sorted({row["policy"] for row in rows}):
    selected = [row for row in rows if row["policy"] == policy]
    times = [row["result"]["virtual_time_s"] for row in selected]
    success = sum(
        row["result"]["success"] and row["result"]["cleared_count"] == 16
        for row in selected
    )
    print(policy, {
        "n": len(selected),
        "success_16": success,
        "mean_s": round(statistics.mean(times), 3),
        "median_s": round(statistics.median(times), 3),
        "min_s": round(min(times), 3),
        "max_s": round(max(times), 3),
    })
PY
```

查看某个策略前几个案例的路线和动作诊断：

```bash
task2/.venv/bin/python -m task3.experiments.inspect_routes \
  task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz \
  --policy candidate_020_grid5_center_approach \
  --first 3
```

若希望用编辑器查看解压文本，不要在正式结果目录产生重复大文件，可解压到 `/tmp`：

```bash
gzip -cd task3/results/raw/optimization/manual_pair_020_smoke.jsonl.gz \
  > /tmp/manual_pair_020_smoke.jsonl
```

通常优先使用第6.3节的 `analyze_results` 生成CSV和图表，只有排查具体动作时才读取原始JSONL。

### 6.5 什么时候本地 Benchmark 才算数

1案例只验证程序能运行，20案例只算 smoke。策略性能要稳定后才算数：

- development：至少200个固定16源配对案例；
- stability：三组互不重叠、每组至少100案例；
- final holdout：至少500个从未参与调参的案例；
- 所有批次必须100%清除；
- 相同种子重复运行结果应一致；
- 候选相对冠军的配对 bootstrap 95%区间下界应大于0；
- 达到3500 s需要holdout均值和均值95%区间上界都不超过3500 s。

完整种子协议和晋级标准见 `prompt2.md` 与 `report/strategy_optimization.md`。不得更换不利种子、删除失败案例或用单批偶然成绩宣称策略更优。

### 6.6 复现原始混合源数实验

下面的命令生成10--16源混合案例，用于复现历史结果，不用于固定16源的3500 s结论：

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

## 7. 如何手动进行在线模拟器演练

在线命令会立即发送 `/enter` 和后续动作。运行前必须确认Windows GUI处于“问题3演练”，不得误选正式测试。

### 7.1 演练前检查

1. 先运行第6.1节全部测试，必须全部通过；
2. Windows模拟器已经登录，明确进入“问题3演练测试”；
3. 点击开始新一局，等待接口就绪；
4. 记录这一局新生成的案例编码；
5. 确认日志目录可写；
6. 不要复用已经结束的案例编码。

模拟器运行在 Windows、算法运行在 WSL 时，先确保 Windows 端口可从 WSL 访问。服务地址必须作为当次参数传入，不要写进源码、Git 配置或提交的 `.env`。可先检查：

```bash
nc -vz '<Windows 可达地址>' '<模拟器端口>'
```

成功时会显示类似：

```text
Connection to <地址> <端口> succeeded!
```

如果WSL设置了HTTP代理，应确保模拟器地址走 `NO_PROXY`，不要把本地模拟器请求转发到外部代理。不要把代理或地址持久化进仓库。

### 7.2 运行稳定 Geometry 冠军

当前稳定默认策略是注册表中的 `champion_000_geometry_baseline`：

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<当前登录参赛队号>' \
  --base-url 'http://<Windows 可达地址>:<端口>' \
  --case-id '<本局新案例编码>' \
  --policy champion_000_geometry_baseline
```

### 7.3 运行指定候选策略

例如运行020策略：

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<当前登录参赛队号>' \
  --base-url 'http://<Windows 可达地址>:<端口>' \
  --case-id '<本局新案例编码>' \
  --policy candidate_020_grid5_center_approach
```

`--policy` 会自动加载020的 `hybrid + center_approach + 5 m网格 + local_channel_limit=3`。不要再手工补 `--mode` 或 `--local-family`，否则容易误以为测试了020但实际漏掉关键参数。

若只想手动组合历史策略，也可以不用 `--policy`：

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<当前登录参赛队号>' \
  --base-url 'http://<Windows 可达地址>:<端口>' \
  --case-id '<本局新案例编码>' \
  --mode hybrid \
  --local-family geometry \
  --local-action-limit 3
```

每局应使用GUI新生成的案例编码。演练入口会把策略ID、实际模式、选点器和参数写入summary。队号在请求日志和summary中脱敏。

### 7.4 如何判断在线运行成功

终端输出和summary至少应满足：

```text
success = true
cleared_count = GUI真实目标数
coverage_completed = [0,1,2,3,4,5,6]  （清除16个提前结束时可例外）
termination_reason = upper_bound_reached
                  或 coverage_certificate_and_all_found_cleared
```

同时检查：

- `channel_status` 中没有遗留 `found`；
- `unexpected_clear_failure` 为0；
- 日志末尾存在 `accepted=true` 的 `/exit` 响应；
- `known_total` 和 `clear_ratio` 在GUI标注后分别为真实总数和1.0；
- `strategy.policy_id` 与本局计划测试的策略一致。

### 7.5 用GUI真值标注并汇总

GUI 显示真实目标数后，为该局补充分母并重新聚合：

```bash
task2/.venv/bin/python -m task3.experiments.annotate_practice \
  --summary task3/results/raw/practice/<案例-时间>.summary.json \
  --total '<GUI 真实目标数>'

task2/.venv/bin/python -m task3.experiments.analyze_practice \
  --input-dir task3/results/raw/practice \
  --output task3/results/tables/practice_summary.csv
```

原始响应日志和summary默认位于 `task3/results/raw/practice/`，文件名包含案例编码和时间戳。不要修改原始JSONL内容。

### 7.6 异常时怎么做

程序会保存此前已接受的响应和错误summary，并尝试安全 `/exit`。发生连接失败、`accepted=false`、现实截止保护或清除异常时：

1. 不要立即用同一个案例盲目重跑；
2. 保存JSONL和summary；
3. 核对GUI是否仍处于该演练；
4. 检查最后一次 `accepted=true` 响应和 `virtual_time_s`；
5. 修复原因后启动一局新的演练并使用新案例编码。

在线演练只能提供跨案例线索。不同案例的平均时间不能当作严格策略对照；策略晋级仍应以第6.4节的本地固定种子配对Benchmark为准。

## 8. 当前在线演练结果

已完成四次问题 3 演练：

| 案例 | 策略 | 目标/清除 | 清除率 | 总虚拟时间 | 平均时间 | 墙钟时间 | 清除落空 |
|---|---|---:|---:|---:|---:|---:|---:|
| `J2TJ-2H73-YG5X-Y4AZ` | B3 hybrid-shortlist | 16/16 | 100% | 5903.926 s | 368.995 s/个 | 2.910 s | 13 |
| `WBBE-W933-ZBEX-DQ7B` | hybrid-geometry | 12/12 | 100% | 4287.436 s | 357.286 s/个 | 1.867 s | 0 |
| `GRT8-SCD6-UNQG-528K` | champion-000 hybrid-geometry | 14/14* | 100% | 4684.356 s | 334.597 s/个 | 2.753 s | 0 |
| `GKW6-72AQ-J2CJ-DY5A` | candidate-020 grid5-center-approach | 11/11* | 100% | 4774.151 s | 434.014 s/个 | 6.964 s | 0 |

四局都完成 7/7 覆盖且无网络重试。星号表示第三、四局分别由14次和11次成功清除加完整七点不存在证书确定总数，仍需GUI真值作独立交叉核对。020局单位目标移动、切频、检测、光学和激光时间分别为340.105、13.455、75.455、3和2 s；其平均时间为434.014 s/个。不同演练案例不能作为策略的配对因果比较，020也尚未满足离线稳定晋级标准。

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

## 固定 16 源优化记录

离线优化现在支持 `random_scenario(..., source_count=16)` 和
`run_offline --source-count 16`；不传该参数仍保持 10--16 的旧默认行为。可选择的
稳定策略注册表位于 `src/policies.py`。本轮实验记录、固定种子协议和候选去留见
`report/strategy_optimization.md`，种子集合见 `results/raw/optimization/seed_sets.json`。

本轮未完成完整 development/stability/final-holdout 协议，因此历史
`champion_000_geometry_baseline` 仍是默认语义；smoke 最优候选不会被描述为稳定冠军。

# Candidate 039: dynamic open route

Candidate `candidate_039_dynamic_open_route` is intentionally separate from the
historical candidate 038 task queue.  It treats the ordered coverage vertices
as precedence obligations rather than a physical route backbone.  Every plan
starts at the robot's actual position, includes the next two coverage anchors
and every actionable source in the historical-current-progress horizon, and
commits only the first target before replanning.

Sweep progress is the historical maximum directed/unwrapped polar angle, so a
local geometric rollback never rolls the horizon backward.  Each source
resolver exposes exactly one current service target.  Straight movement
segments of every type admit zero-extra-distance observations and clears.  A
hard Angular Crossing Guard checks single-bearing sources before each segment,
using zero-detour measurement first, then a detour of at most 100 m, and finally
a forced second-bearing target.  The older sector/group,
`required_before_advance`, and `AdvanceCoverage` rules remain available only to
candidate 038 and are not imported by the new controller.
