# CUMCM B 题问题 3：自动搜索、定位与清除

本目录实现“七点覆盖证书 + 分频道集合定位 + MEC 安全清除 + 有限覆盖兜底 + 滚动调度”。程序只处理问题 3 的全向源；概率粒子只参与候选排序，不改变硬可行集、清除证书或终止条件。

## 1. 环境

推荐 Python 3.11。问题 3 的依赖单独维护在 `task3/requirements.txt`：

```bash
python3 -m venv task3/.venv
task3/.venv/bin/python -m pip install -r task3/requirements.txt
```

本仓库现有 `task2/.venv` 已包含相同版本的 NumPy、SciPy、Matplotlib 和 pytest，也可直接复用。HTTP 客户端使用 Python 标准库，不依赖 `requests`。

## 2. 模块

- `src/coverage.py`：原点和半径 1200 m 正六边形的解析覆盖证书、旋转与路线；
- `src/geometry.py`：只会放大真实集合的保守单元外包、最小包围圆和 20 m 有限覆盖；
- `src/channel_state.py`：20 个频道的 `unknown -> found -> cleared` / `unknown -> absent` 状态机；
- `src/local_planner.py`：geometry、E-optimal、expected-diameter、MEC/Chebyshev/边界/正交/覆盖复用候选；
- `src/scheduler.py`：SEARCH/LOCALIZE/CLEAR 的滚动评分和可配置防饿死阈值；
- `src/client.py`：严格串行 HTTP、幂等重试、状态码与 `accepted` 双检查、现实截止时间；
- `src/controller.py`：完整运行循环；
- `src/mock_simulator.py`：10–16 个互异频道全向源的题面一致离线环境。

硬集合由闭方格单元的并集表示。只有当解析上下界证明整格不可能时才删除该格。因此它是连续可行集的外包，而不是把内接圆多边形冒充严格集合。MEC 对所有保留单元四角求解并复核；只有半径不超过 `20 - 0.25` m 才清除。兜底时每个保留单元中心放置一个清除圆；默认格长 20 m、半对角线 14.142 m，小于 20 m，所以不存在单元内部缝隙。

`task2/src/strategies/selectors.py` 的 geometry、FIM-E 和 expected-diameter 目标被小范围迁入候选排序；没有直接复用其 `candidate_regions`/Shapely 集合，因为后者使用内接圆多边形和概率筛选，不能承担问题 3 的硬包含层。三类评分在 `local_planner.py` 中集中实现，硬状态仍只有一套 `CellGrid` 语义。

## 3. 测试

```bash
MPLCONFIGDIR=/tmp/task3-mpl task2/.venv/bin/python -m pytest task3/test -q

task2/.venv/bin/python -m task3.experiments.export_coverage_certificate \
  --output-dir task3/results/tables
```

测试覆盖七点坐标及解析证书、0°/360°、随机真值包含、1000 m 无信号排除、`near` 立即清除、非凸外包、MEC 判据、有限覆盖、状态和终止、`/clear` 频道不变、超时幂等重试、拒绝和连接失败，以及四种策略的端到端清除。

## 4. 离线配对实验

默认命令生成同一批 100 个场景上的四主策略、三种局部选点和防饿死阈值 1/3/5 的配对结果：

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

压缩 JSONL 首行记录完整配置、Git 状态和误差模型；SHA-256 manifest 固定当前实现与产物版本；后续每行含案例编码、种子、源真值、动作序列、响应摘要、算法墙钟时间、模拟器虚拟时间和时间分解。误差由“场景种子 + 频道 + 位置”确定，同地点重复检测不会产生独立误差。分析按案例 bootstrap，输出 mean、median、P90、P95、max 和 95% 区间。

## 5. 模拟器演练（不会启动正式测试）

先在模拟器 GUI 中登录并明确选择“问题 3 演练测试”，等待接口就绪；队号、端口和案例编码只从当次命令传入，不写入仓库：

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<当前登录参赛队号>' \
  --base-url http://127.0.0.1:2026 \
  --case-id '<界面案例编码>'
```

演练结束后，GUI 才会显示真实目标数。用该数标注刚生成的 summary（不要为了填写分母重跑随机案例）：

```bash
task2/.venv/bin/python -m task3.experiments.annotate_practice \
  --summary task3/results/raw/practice/<案例-时间>.summary.json --total 13

task2/.venv/bin/python -m task3.experiments.analyze_practice \
  --input-dir task3/results/raw/practice \
  --output task3/results/tables/practice_summary.csv
```

清除比例必须以 GUI 真值为分母。原始动作日志与 summary 默认保存在 `task3/results/raw/practice/`。若异常，程序在 summary 中保存错误，已接受响应此前已逐条写入 JSONL。

本仓库故意不提供“正式测试启动”脚本。正式测试仅能在用户当前明确确认后进行，并须先冻结代码与参数、保留三份模拟器原始加密日志且不改名。命令行程序无法替代 GUI 对“演练/正式”模块的确认。

## 6. 常用参数

`--local-action-limit` 默认 3；阈值达到后强制前往下一覆盖点。`--mode` 可取 `two_stage`、`enroute`、`rolling_hard`、`hybrid`；`--local-family` 可取 `geometry`、`e_optimal`、`expected_diameter`、`shortlist`。默认混合策略为 `hybrid + shortlist`，随机种子 20260911。

正常终止仅有两种：成功清除 16 个；或七点存在性扫描全部完成、其余频道均有不存在证书且所有已发现频道清除。覆盖完成但清除少于 10 个会返回失败；现实截止保护、通信异常和动作上限也均作为异常退出记录，不能算有效成功样本。
