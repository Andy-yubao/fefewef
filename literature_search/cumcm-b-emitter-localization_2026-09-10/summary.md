# CUMCM B题 Literature Search — Round 1

Run: `literature_search/cumcm-b-emitter-localization_2026-09-10/`
Level: **L1, further constrained** (3 facets A/B/C, 2 buckets — A arXiv + C OpenAlex, wave 1 only)
Date: 2026-09-10
Queries issued: 14 (arXiv 9, OpenAlex 5). Zero-return queries: 2. Failed queries: 2.
Not done: PDFs, full text, Crawl4AI, citation snowball, Asta, clusters D/E/F.

Execution note: the fan-out was run inline rather than via per-bucket subagents. The brief's
budget (≤3 queries per cluster, ≤8 hits per query) is far below this skill's L1 default
(3 facets × 4 buckets × 15 hits), so spawning searchers would have added cost without adding
coverage. All queries, including the failures, are recorded in `raw/arxiv.json` and
`raw/openalex.json`.

---

## 1. Executive Summary

B 题的数学内核，文献里对应三条**彼此独立**的研究线，而本轮最重要的发现是：这
三条线在索引文献中**没有接上**。

**问题 1**（方向观测 + ±1° 硬误差 → 定位区域 → 直径）落在 *set-membership /
bounded-error estimation* 与 *bearings-only localization* 的交集上。这个交集在
arXiv 上按精确短语检索返回 **0 条**（两种拼写各测一次），OpenAlex 上两个术语
返回的结果集分属完全不重叠的两个社区（控制理论 vs 信号处理）。set-membership
一侧成熟工具是椭球与 zonotope 的**包含性保证**（Bertsekas 1971；Ge 2017；
Ben Chabane 2014）；bearings-only 一侧成熟工具是 ML/TLS 点估计与 CRLB
（Doğançay 2005；Kaplan 2001）。**没有任何一篇把"有界角度误差"直接表示成可行
多边形并求交。**

**问题 2**（第二观测点选择）是三条线中最成熟的一条。Zhao–Chen–Lee 用 frame
theory 给出了 2D/3D 最优布站的**充要条件与显式构造算法**；Yang 等 2013 给出了
在**任意高斯先验**下最大化更新后 FIM 的放置准则——这正是"已测一次，下一步放哪
里"的正确形式；Tang 等 2025 用 A-optimality（min trace CRB）给出了含 AOA 的
最优几何约束与最优夹角。这三篇可以支撑问题 2 的建模与验证。

**问题 3**（搜索 + 定位 + 清除）对应 *active sensing / informative path
planning*。成熟的是**目标函数**：det(FIM)（Oshman 1999；Xiao 2026）、CRLB
（Dehghan 2014）、posterior entropy（Habibi 2026）。Dehghan 等 2014 在 RF +
UAV 域内做的"在候选航点中选下一个使 det(FIM) 最大者"，与 B 题的决策环结构
几乎一一对应。

**最关键的方法论缺口**：所有路径规划与布站文献都以**高斯噪声方差**为前提，
而题目给的是**硬上下界 ±1°**。把硬界映射成方差是一个必须自行论证的建模决策，
现有文献没有回答。而正因为我们的可行集可以**精确**算出（角扇区求交 = 凸多边形
半平面求交），我们可以绕开这个不匹配：直接用"下一次观测使可行多边形**直径**最小"
作为分布无关的准则。这条路线比文献里的椭球/zonotope 近似**更精确也更简单**，
但**直径作为精度指标在文献中不存在**，需要自行设计。

**下一轮最该深读**：Zhao–Chen–Lee（最优几何的闭式结果）、Yang 2013（带先验的
放置）、Tang 2025（AOA 的 A-optimality 显式约束）、Dehghan 2014（RF+UAV 的单步
信息决策），以及 Oshman 1999（轨迹级 det(FIM) 的经典框架）。

---

## 2. Problem A — Bounded-error localization

### 检索观察

- arXiv 精确短语 `"bearing-only" AND "set-membership"` → **0 条**；复数拼写
  `"bearings-only" AND "set-membership"` → **0 条**。
- 去掉引号改为裸词后 arXiv 返回正常（`bearings-only localization` → 6 条，
  `bounded error bearing localization feasible region interval` → 6 条，但后者被
  math.OC 的 "feasibility problem" 文献淹没）。
- OpenAlex 上 `bearing-only localization set-membership` **失败**：`bearing`
  被解析为机械轴承，返回轴承故障诊断论文。改用 `set-membership estimation`
  后命中该领域的完整经典谱系。
- 结论：**这是两条互不相交的文献社区**，不是检索失误。

### 候选论文

| Title | Year | Core method | Uncertainty representation | Direct relevance to B | Grade | DOI/arXiv |
|---|---|---|---|---|---|---|
| Recursive state estimation for a set-membership description of uncertainty | 1971 | 递归集员滤波；能量约束→椭球，瞬时约束→包围椭球 | 椭球（有界集） | 提供了"测量+有界误差→相容状态集"的奠基形式；问题 1 是其静态几何特例，但动态递推机制不需要 | BACKGROUND | 10.1109/TAC.1971.1099674 |
| Optimal estimation theory for dynamic systems with set membership uncertainty | 1991 | 集员估计的最优性理论（插值、有界噪声） | 可行集 | 确立"最小化可行集大小"为规范最优性准则，支撑我们的指标选择 | BACKGROUND | 10.1016/0005-1098(91)90134-N |
| A Dynamic Event-Triggered Transmission Scheme for Distributed Set-Membership Estimation | 2017 | 分布式集员估计，UBB 噪声，包围椭球上的递归凸优化 | **保证包含真值的包围椭球** | "保证包含"性质正是问题 1 对定位区域的要求 | USEFUL | 10.1109/TCYB.2017.2769722 |
| Improved set-membership estimation approach based on zonotopes and ellipsoids | 2014 | zonotope→椭球混合集员估计，P-radius 切换准则 | **zonotope**（Minkowski 和下的多面体） | zonotope 对 Minkowski 和与求交封闭——累积角扇区求交的天然代数；仅切换准则与动态系统绑定 | **ANCHOR** | 10.1109/ECC.2014.6862412 |
| Ellipsoidal state-bounding-based set-membership estimation with UBB disturbances | 2016 | 预测-校正集员递推；**最小化可行椭球集体积** | 椭球，体积作指标 | 提供"收缩可行集体积"这一目标——正是问题 1"区域直径/面积作精度"的类比物 | USEFUL | 10.1049/iet-cta.2015.0654 |
| Set-membership estimation for linear time-varying descriptor systems | 2020 | 描述子系统的集员估计 | 可行集 | 几何不可迁移 | DROP | 10.1016/j.automatica.2020.108867 |
| H∞-optimal Interval Observer Synthesis via Mixed-Monotone Decompositions | 2022 | 区间观测器，构造即保证包含 | 区间（盒子） | 区间/盒子表示概念可迁移；LMI/SDP 机制不可 | BACKGROUND | arXiv:2203.07430 |
| Distributed Resilient Interval Observer Synthesis | 2024 | 分布式区间观测器，ℓ1 误差界最小化 | 区间 | 同上，另加"最小化误差界" | BACKGROUND | arXiv:2401.15511 |
| Distributed Bearing-based Formation Control and Network Localization with Exogenous Disturbances | 2020 | 鲁棒稳定性；**方向测量定位误差的显式上界集** | 定位误差的界集 | 极少数把*方向测量*与*显式有界误差集*耦合的工作；但框架是编队控制而非交会定位 | USEFUL | arXiv:2007.07458 |
| Target localization from bearings-only observations | 1997 | 不预设误差为随机或系统的估计方法；可观测性分析 | 非概率误差描述 | 罕见的非贝叶斯 bearings-only 估计；与有界误差思路相邻，但无集合表示 | BACKGROUND | 10.1109/7.570703 |
| Networked pointing system: bearing-only target localization and pointing control | 2025 | 方向估计 + 指向控制；可定位性条件 | — | 给出最小可定位条件（两智能体与目标不共线），可作问题 2 候选区域的合法性下界 | USEFUL | arXiv:2506.18460 |

### Best anchor papers

- **Ben Chabane et al. 2014**（zonotope/椭球混合集员，`10.1109/ECC.2014.6862412`）—
  唯一的 A 级：zonotope 代数是最接近凸多边形可行集的现成工具。
- 次级桥梁：**Ge et al. 2017**（保证包含性质）、**Liu et al. 2016**（可行集体积最小化）。

**明确结论：本簇没有找到任何直接 ANCHOR。** 没有一篇文献做"有界角度误差下的
方向线求交 → 多边形 → 直径"。问题 1 的算法需要自行设计——但这是**好消息**：
题目要求的构造比文献里的椭球/zonotope 近似更简单，可以精确求解。

---

## 3. Problem B — Optimal observation geometry

### 候选论文

| Title | Year | Core method | Optimization criterion | Key geometric result | Direct relevance to B | Grade | DOI/arXiv |
|---|---|---|---|---|---|---|---|
| Optimal sensor placement for target localisation and tracking in 2D and 3D | 2013 | frame theory 统一 bearing-only / range-only / RSS | FIM 型最优性 | 2D/3D 最优放置的**充要条件**；regular/irregular 两类；梯度控制律可构造 | 问题 2 的数学内核：闭式最优几何 | **ANCHOR** | 10.1080/00207179.2013.792606（arXiv:1210.7397） |
| Optimal placement of bearing-only sensors for target localization | 2012 | FIM + frame theory，仅 bearing-only | FIM 最优性 | 两类最优放置；**显式构造算法**；irregular 可降维转为 regular | 上篇的会议版，补齐构造算法 | **ANCHOR** | 10.1109/ACC.2012.6314884 |
| Optimal Placement of Heterogeneous Sensors for Targets with Gaussian Priors | 2013 | 从**任意高斯先验**出发最大化**更新后** FIM；异构传感器含 bearing-only；多步 | 更新后 det(FIM) | 任意先验下的最优放置条件；传感器可多次不同精度的独立测量 | **与问题 2 结构完全同构**：测一次→先验→选第二测点 | **ANCHOR** | 10.1109/TAES.2013.6558009 |
| Optimal Sensor Placement Using Combinations of Hybrid Measurements | 2025 | TDOA/RSS/**AOA**/TOA 组合的 CRB | **A-optimality：min trace(CRB)** | 各测量类型的最优几何约束，含 AOA 的显式结果 | "最优夹角"的直接文献来源 | **ANCHOR** | arXiv:2504.03769 |
| Improving D-Optimal Sensor Placement for Bearing-Only Localization via Maximum-Entropy Reweighting | 2026 | 两层：KL 散度粒子重加权 + 重加权 FIM 上的 D-最优放置 | **D-optimality（det FIM）** | 两层解耦：重加权跨模态通用，放置专属方向几何；多源 | 最新且直接是 bearing-only 布站，明确多源 | **ANCHOR** | arXiv:2605.11116 |
| Optimization of observer trajectories for bearings-only target localization | 1999 | 最优控制（微分包含） | **max det(FIM)**，带状态约束 | 最优观测者轨迹；机动提升可观测性 | 横跨 B/C：同一准则的动态版 | **ANCHOR** | 10.1109/7.784059 |
| Optimal Sensor Placement for Source Localization: A Unified ADMM Approach | 2021 | CRLB 统一 + ADMM/MM 求解器 | A / D / E-最优性可切换 | 统一求解器，可不近似准则、可处理相关噪声 | **优化器模板**；测量类型为 TOA/TDOA/RSS | USEFUL | arXiv:2109.03639 |
| Optimal Sensor Placement for Multiple Target Positioning with Range-Only Measurements | 2013 | 传感器位置上的凸优化 | **最大化跨目标的 log det FIM 凸组合** | 最优构型显式依赖约束、目标位置与先验不确定度 | 多目标目标函数形式 → 问题 3 | USEFUL | 10.3390/s130810674 |
| Multisensor-Multitarget Bearing-Only Sensor Registration | 2016 | 融合节点上的 ML 偏差估计 | 推导 CRLB | 偏差仅有机动下可辨识 | bearing-only 的 ML 估计 + CRLB | USEFUL | arXiv:1603.03450 |
| Relationship Between Geometric Translations and TLS Estimation Bias in Bearings-Only Target Localization | 2008 | TLS 估计偏差分析 | — | 估计偏差依赖**坐标原点位置** | 题目把原点固定在圆域中心——这是一个真实的设计注意事项 | BACKGROUND | 10.1109/TSP.2007.909052 |
| Fisher-Information-Based Sensor Placement for Structural Digital Twins | 2026 | 伴随法算 FIM 乘积，D-最优 log-det | D-optimality（log det） | 区分 **detectability 与 localizability** | 仅概念层面（结构力学） | BACKGROUND | arXiv:2602.02981 |
| Outlier Detection and Optimal Anchor Placement for 3D Underwater Optical WSN | 2018 | 半二次最小化 | **D-optimality**（组合 FIM） | 满足 D-最优性的锚点布置 | 方法桥梁 | BACKGROUND | arXiv:1810.03110 |

### FIM / CRLB / GDOP、A-/D-最优性、最优角度之间的关系

- **FIM 是共同底座**：给定方向测量的似然，单次角度测量的 FIM 对目标位置的贡献
  正比于 1/σ² 与 1/r²。Zhao–Chen–Lee、Bhattacharya、Oshman 都以此为起点。
- **CRLB = FIM⁻¹**，是协方差的下界；因此"最大化 FIM"与"最小化 CRLB"是同一件事
  的两种写法。CRLB 的**几何含义是误差椭球**（uncertainty ellipse）。
- **A-optimality = min trace(CRB)**，即最小化误差椭球**半轴平方和**；Tang 2025 与
  Sahu 2021 用它，因为 trace 是凸的、便于优化。
- **D-optimality = max det(FIM)**，即最小化误差椭球**体积**（det(CRB) 最小）；
  Dehghan 2014、Bhattacharya 2026、Oshman 1999 用它，因为行列式对几何构型最敏感。
- **GDOP** 是 CRLB 的归一化标量形式（在测距/测角精度已归一后），本簇检索未直接
  命中以 GDOP 命名的 B 簇论文——这是 OpenAlex 术语层面的一个检索缺口。
- **最优角度**：在 2D、两个测点、目标固定且距离固定的设定下，最优构型由
  frame theory 的充要条件给出；直观结果是两视线的**交会角趋近 90°**（交会角正弦
  最大）。Xiao 2026 把这一点直接写成"intersection angle sine term"加入目标函数，
  与 Tang 2025 的 AOA 几何约束互为印证。

**对问题 2 的直接价值**：Zhao–Chen–Lee 给闭式最优几何，Yang 2013 给"有先验时"
的放置准则，Tang 2025 / Xiao 2026 给最优夹角的可比较数值。三者结合足以支撑
"第二检测点候选区域"的建模与论证。

---

## 4. Problem C — Active sensing / path planning

### 候选论文

| Title | Year | Core method | Planning objective | Uncertainty metric | Single-step or trajectory | Direct relevance to B | Grade | DOI/arXiv |
|---|---|---|---|---|---|---|---|---|
| Optimization of observer trajectories for bearings-only target localization | 1999 | 最优控制 / 微分包含 | max det(FIM)，带状态约束 | FIM det | **轨迹**（全局最优控制） | 问题 2→3 的桥梁：轨迹级信息最优的经典范式 | **ANCHOR** | 10.1109/7.784059 |
| Optimal path planning for DRSSI based localization of an RF source by multiple UAVs | 2014 | EKF + 候选航点上的局部 CRLB | 在下一候选航点上 max det(CRLB⁻¹) | CRLB / 估计不确定区域 | **单步前瞻**（离散候选集） | 与问题 3 决策环**结构同构**，且同在 RF+UAV 域 | **ANCHOR** | 10.1109/IROM.2014.6990961 |
| Path planning for localization of an RF source by multiple UAVs on the Crammer-Rao Lower Bound | 2013 | 局部 CRLB 上的最速下降 + 空间离散 | min CRLB 标准差 | CRLB | 单步 | 上篇的前身，同一课题组 | USEFUL | 10.1109/IROM.2013.6510083 |
| GyroCopter: Differential Bearing Measuring Trajectory Planner for Tracking and Localizing RF Sources | 2024 | 利用飞行动力学做恒定陀旋产生"伪方位"测量；推导最优旋转速度 | 方位获取效率 | — | **轨迹**规划，多 RF 源，实地验证 | 唯一处理**多 RF 源**的方位获取规划，机器狗循环的多目标类比 | **ANCHOR** | arXiv:2410.13081 |
| Trajectory Optimization in Single and Dual-UAV Bearing-Only Target Localization | 2026 | 谱加权 FIM 目标 + 带运动约束的 PSO | 谱加权 FIM；双机加交会角正弦项 | FIM（谱） | **轨迹**，单机与双机 | 最新 bearing-only 轨迹优化；交会角项即"最优夹角"的工程化表达 | **ANCHOR** | arXiv:2606.09188 |
| A Bearing-Strength Method for Motion Estimation of Unknown Energy Emitters | 2026 | 方位 + 接收强度融合 | 可观测性 | 可观测性条件 | 运动策略分析 | 明确指出 bearing-only 的可观测性**要求横向运动**，加场强可解除该要求；题目的测向机正是"方位+场强" | **ANCHOR** | arXiv:2607.12515 |
| RF Source Seeking using Frequency Measurements | 2018 | 多普勒频率反馈 + 方位扰动 | 逼近辐射源 | — | 连续自适应轨迹 | 圆周运动消解方向二义性，收敛到源附近 | USEFUL | arXiv:1803.02494 |
| Adaptive Informative Path Planning with Multimodal Sensing | 2020 | POMDP + POMCP，约束可行性 | 信息增益 vs 能量，**在多个传感器间选择** | belief 熵 | 轨迹（滚动时域） | POMDP 框架可承载"切换频道"的离散动作与代价 | USEFUL | arXiv:2003.09746 |
| Multi-UAV Active Sensing with Information Gain-based Planning and Belief Fusion | 2026 | 因子图 belief map + IGbIPP | 信息增益（对比熵下降） | 熵 / 建图误差 | 轨迹（滚动时域） | 通用 IPP 模板 + 多机信念融合 | USEFUL | arXiv:2606.10986 |
| Homotopic information gain for sparse active target tracking | 2026 | 同伦信息增益，是度量信息增益的下界 | 同伦信息增益 | 信息增益 | 轨迹 | 稀疏观测下的信息增益度量思路 | USEFUL | arXiv:2602.17926 |
| Bearings-only target localization for an acoustical unattended ground sensor network | 2001 | 准 ML + 方位关联 | — | — | 静态，多目标 | 多源**数据关联**（问题 3/4 必须解决的一步） | USEFUL | 10.1117/12.441279 |
| Measurement Testbed for Radar and Emitter Localization of UAV at 3.75 GHz | 2022 | 测量试验台 | — | — | 硬件 | 背景 | BACKGROUND | arXiv:2210.07168 |
| Multi-Robot IPP / Active Markov ITPP / Online IPP for 3D Surface | 2011–2021 | GP 上的熵与互信息 IPP | 熵、互信息 | GP 后验 | 轨迹 | 通用 IPP 背景，非 RF | BACKGROUND | arXiv:1302.0723 / 1101.5632 / 2103.09556 |

**失败查询记录**：`UAV radio source localization path planning trajectory optimization`
返回的 6 条**全部**是通用 UAV 轨迹规划（自主着陆、系绳 UGV-UAV、AoI 数据采集、
δ-spaces），无一条涉及辐射源。改用 `radio emitter geolocation UAV search bearing
measurements` 后命中率大幅提升——说明"UAV + trajectory optimization"会淹没
"RF source" 这一语义。

**规划目标统计**（题目第 3 节要求判断的）：
- det(FIM) / 最大化信息矩阵行列式：Oshman 1999、Dehghan 2014、Bhattacharya 2026
- min trace(CRLB)（A-optimality）：Tang 2025、Sahu 2021
- posterior entropy：Habibi 2026、Choudhury 2020、Cao 2013
- **未出现**：uncertainty-set volume（仅出现在集员估计一侧，Liu 2016）、
  首次发现概率（本簇未检索到——属 D 簇范畴）

---

## 5. Cross-cluster synthesis

### 统一建模链是否被文献支持

```
方向观测
   ↓
bounded-error / probabilistic localization
   ↓
当前不确定区域
   ↓
FIM / CRLB / area / entropy 评价指标
   ↓
选择下一观测位置
   ↓
trajectory / path planning
   ↓
新的方向观测  →  继续缩小不确定性
```

**判断：这条链在文献中只被"分段"支持，接缝恰好落在 B 题最独特的地方。**

| 环节 | 文献状态 | 说明 |
|---|---|---|
| ① 方向观测的 FIM | ✅ **成熟公式可直接借用** | 单次方位测量的 FIM 是标准结果，见 Zhao 2013、Oshman 1999、Tang 2025、Xiao 2026 |
| ② 有界误差 → 可行区域 | ⚠️ **形式借用，构造自建** | 集员估计提供"保证包含"的形式与 zonotope 代数（Bertsekas 1971；Ge 2017；Ben Chabane 2014），但都在动态系统语境。B 题的可行集 = 角扇区求交 = **凸多边形**，可精确计算（半平面求交），比文献的椭球/zonotope 近似更精确 |
| ③ 不确定度指标 | ❌ **需自行设计** | 文献只提供 volume / det FIM / trace CRB / entropy；**直径（diameter）不存在于检索到的文献中**，而题目第 1 问明确要求直径 |
| ④ 下一观测位置选择 | ✅ **准则可直接借用** | Dehghan 2014 就是"候选航点中选 det(FIM) 最大者"；Yang 2013 给"有先验时"的更新准则；Zhao 2013 给闭式最优几何 |
| ⑤ 轨迹 / 路径规划 | ✅ **框架可借用** | Oshman 1999（最优控制 + det FIM）、Xiao 2026（谱加权 FIM + PSO）、GyroCopter 2024（bearing 获取 + 多源 + 实地验证） |
| ⑥ 联合优化（搜索+定位+清除） | ❌ **需自行设计** | 见下方缺口 4/5 |

### 已有成熟公式、可直接借用的部分

1. 方位测量的 FIM 与 CRLB（含 1/r² 距离衰减），以及 det/trace 两种最优性准则的
   等价关系。
2. 最优观测几何的**充要条件与构造算法**（Zhao–Chen–Lee frame theory）。
3. 在**已有先验**下最大化更新后 FIM 的放置准则（Yang 2013）——问题 2 的正确形式。
4. 单步前瞻式"下一个航点用 det(FIM) 选"的完整流程（Dehghan 2014）。
5. 集员估计的**保证包含**要求（真值必在集合内）与可行集收缩的优化框架。

### 需要我们自行设计的部分

1. **可行集的精确几何构造**：角扇区（顶点 + 两条射线）的表示、半平面求交、
   增量式求交更新、顶点集维护与退化处理（近共线、扇区不交）。
2. **直径算法**：凸多边形直径（旋转卡壳 / 凸包），以及两测点特殊情形下
   四边形 6 对顶点距离的闭式比较；题目还要判断"以直径为直径的圆能否覆盖"。
3. **有界误差下的"下一测点"准则**：这是**最关键的建模决策**。两条路线：
   - (a) 把 ±1° 解释为均匀分布，σ² = (2°)²/12，然后沿用 FIM/CRLB 体系；
   - (b) 完全留在有界误差世界，直接选使**求交后可行多边形直径最小**的候选点，
     分布无关。
   路线 (b) 在数学上更干净、更贴合题目，且**正因为我们能精确算出可行集才可能**，
   但现有文献不做这件事——这既是风险也是论文的贡献点。建议以 (b) 为主线、
   (a) 作对照与敏感性分析。
4. **B 题特有的代价结构**：频道切换 1 s/跳、单次检测 5 s、光学精确定位 3 s、
   清除 2 s、进入 20 m 内才能清除、机器狗 5 m/s、20 分钟硬上限、目标数未知
   10–16。检索到的规划工作都没有这个代价模型。
5. **搜索与清除的联合策略**：目标数未知 + 需先发现再定位。

---

## 6. Recommended Deep Reading Set

按优先级排序，进入下一轮全文阶段。

1. **Zhao, Chen & Lee — Optimal Sensor Placement for Target Localization and Tracking
   in 2D and 3D**（Int. J. Control 2013；`10.1080/00207179.2013.792606`；预印本
   arXiv:1210.7397）。问题 2 的数学内核全在充要条件和构造算法里，摘要写不下。
2. **Yang, Kaplan, Blasch & Bakich — Optimal Placement of Heterogeneous Sensors for
   Targets with Gaussian Priors**（`10.1109/TAES.2013.6558009`）。唯一"已有一次
   测量/先验，下一次放哪里"的现成形式化，直接对应问题 2 的表述。
3. **Tang, Xu, Yang, Kong & Ma — Optimal Sensor Placement Using Combinations of
   Hybrid Measurements**（arXiv:2504.03769）。A-optimality 下 AOA 的显式最优几何
   约束，用来校准我们算出的"最优夹角"是否与文献一致。
4. **Oshman & Davidson — Optimization of observer trajectories for bearings-only
   target localization**（`10.1109/7.784059`）。轨迹级 det(FIM) 的经典范式，是
   问题 2 与问题 3 之间的桥。
5. **Dehghan, Moradi & Shahidian — Optimal path planning for DRSSI based localization
   of an RF source by multiple UAVs**（`10.1109/IROM.2014.6990961`）。RF+UAV 域内
   与问题 3 决策环最接近的实现，单步前瞻选航点。
6. **Xiao, Huang, Li, Shang & Guan — Trajectory Optimization in Single and Dual-UAV
   Bearing-Only Target Localization**（arXiv:2606.09188）。最新的 bearing-only
   轨迹优化；"交会角正弦项"给出了最优夹角的工程化写法。
7. **Chen, Rezatofighi & Ranasinghe — GyroCopter: Differential Bearing Measuring
   Trajectory Planner**（arXiv:2410.13081）。唯一的多 RF 源方位获取规划 + 实地
   验证，是问题 3/4 多目标循环的类比。
8. **Ben Chabane, Stoica, Álamo, Camacho & Dumur — Improved set-membership estimation
   based on zonotopes and ellipsoids**（`10.1109/ECC.2014.6862412`）。zonotope
   代数是我们构造问题 1 可行集的唯一现成工具来源。
9. **Bhattacharya — Improving D-Optimal Sensor Placement for Bearing-Only Localization
   via Maximum-Entropy Reweighting**（arXiv:2605.11116）。最新、多源、直接
   bearing-only 的布站工作，可用于问题 3/4 的后验收缩设计。

---

## 7. Search Gaps

只列本轮**真实存在**的缺口。

1. **有界误差 × 方向定位的交集为空。** 两次精确短语 arXiv 查询（单复数各一）
   返回 0；OpenAlex 上两个术语的结果集分属不重叠社区。
   （诚实caveat：arXiv 的引号+AND 形式在其它查询上也失败过，所以"arXiv 上为 0"
   部分是查询方言造成的假阴性；但 OpenAlex 的社区不相交是独立证据。）
2. **没有文献用可行区域的"直径"作为定位精度指标。** 文献用可行集体积、
   det/trace(FIM 或 CRB)、posterior entropy。题目第 1 问明确要求直径。
3. **所有 FIM/CRLB 布站与规划文献都假设高斯（方差给定）测量噪声**，而题目给的是
   ±1° 硬上下界。"硬界→方差"的映射是一个没有任何检索到的文献为其背书的建模假设。
4. **规划工作几乎都是单目标，或多目标但目标数已知。** 问题 3/4 目标数未知
   （10–16）且需要**先发现**再定位。唯一的多数 RF 源工作（GyroCopter 2024）处于
   已捕获后的跟踪阶段。
5. **没有文献建模 B 题的代价结构**：离散频道切换（1 s × 频道距离）+ 固定 5 s
   检测 + 20 m 内 3 s 光学 + 2 s 清除，且受 20 分钟硬上限约束。最接近的是
   POMDP 多模态传感（Choudhury 2020），但代价模型不同。
6. **GDOP 术语未命中 B 簇论文。** 用该词检索的 B/C 簇结果里没有以 GDOP 命名的
   工作——可能是 OpenAlex 对缩写术语的检索弱点，不代表文献不存在。
7. **仅检索了英文源。** B 题是中文学科竞赛题，"交会定位""示向度""测向"等
   术语可能存在中文文献（CNKI/万方），arXiv 与 OpenAlex 均不索引。本轮未检索。
8. **E 簇（定向干扰源 / 有限视场）与 F 簇（negative information）按指示未系统检索。**
   意外命中的相关线索：Chen et al. 2026（arXiv:2607.12515）关于"横向运动是可观测性
   必要条件"的分析，与问题 4 的定向源排查条件可能相关。未发现自然出现的
   negative-information 论文。

---

## 8. Next-step Recommendation

**推荐 C（A + B）：对 anchor papers 获取全文深读，同时针对缺口做第二轮 L2。**

**理由：**

*需要 A（深读全文）*：9 篇推荐文献里，问题 2 所需的**闭式最优几何条件**（Zhao–Chen–Lee
的充要条件与构造算法）、**AOA 的 A-optimality 显式约束**（Tang 2025）、
**带先验的更新后 FIM 准则**（Yang 2013）都无法从摘要重建——摘要只说了"证明了充要
条件"，具体条件必须看正文。这些直接决定问题 2 的模型能否写出来。

*需要 B（针对性 L2）*：缺口 1/3 是本轮最关键的发现——整个规划文献建在高斯噪声
假设上，而题目是硬界。这不是"再多读几篇"能解决的，需要换词汇重搜。第二轮 L2
应当：
- 换用 **guaranteed / robust / interval / set-inversion / worst-case / minimax
  feasibility** 这一族术语，而不是 set-membership 单打；
- 明确加入 **"intersection of angular sectors"、"angle-only triangulation region"、
  "bearing polygon"** 这类几何描述词；
- 纳入**中文文献源**（缺口 7）；
- 把 D 簇（多目标搜索+定位+路径）正式纳入，因为问题 3 的主体在那里，本轮按指示
  未展开。

**不建议**在下一轮做 citation snowball——本轮 corpus 的强项已集中在 5 个课题组，
snowball 会放大既有偏差，而不是补上缺口。

**本轮完成。不进入下一轮。**
