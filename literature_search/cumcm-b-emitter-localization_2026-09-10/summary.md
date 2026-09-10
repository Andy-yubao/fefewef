# CUMCM B题 Literature Search — Round 1 (corrected)

Run: `literature_search/cumcm-b-emitter-localization_2026-09-10/`
Level: **L1, further constrained** (3 clusters A/B/C, 2 buckets — A arXiv + C OpenAlex, wave 1 only)
Date: 2026-09-10 (corrected same day)

> **Round 1 correction.**
> An initial interpretation that bounded-error set-membership estimation and
> bearing-only localization were disjoint literature communities was **invalidated by
> targeted follow-up retrieval**. The intersection is well populated: bounded
> bearing-only set-membership is an existing research line, and bounded-uncertainty
> sensing over convex polygonal measurement subsets has been formalised since 2006.
> The invalid conclusion has been **removed from the body of this report**, not
> patched at the end. Supplementary provenance is in
> `raw/round1_correction_A.json`; the Round 1 raw files are preserved unchanged.
>
> **Second correction (final pass, no new searches).** The first correction pass
> *also* judged the 2017 paper A1 to be a **conflation** of the 2014 and 2016 papers.
> **That judgement was wrong and is now retracted.** A1 exists: it is a
> Chinese-language journal article that neither OpenAlex nor Crossref returned. This
> is the same false-negative pattern as above, in its worst form — absence from two
> indexes was read as absence of the paper. See §2.1 and correction-table row 9.

### Corrections applied in this revision

| # | Round 1 claim | Status | Corrected statement |
|---|---|---|---|
| 1 | "有界误差 × 方向定位 是两个互不相交的文献社区" | **撤回** | 检索假阴性。该交集存在且有多篇直接论文（见 §2） |
| 2 | "diameter 在文献中不存在，需自行设计" | **缩小断言** | 集合尺度（set diameter / worst-case error / area / radius）是既有指标族；**与本题同构的"角扇区精确求交→多边形→欧氏直径"直接论文未检索到**，这才是缺口所在 |
| 3 | "zonotope 对 Minkowski 和与求交封闭" | **错误，已改** | 普通 zonotope 对 affine/linear 变换与 Minkowski 和封闭，**一般不对交集封闭**；精确求交需 constrained zonotope / zonotope bundle / 外近似 |
| 4 | 问题 1 表述为需要椭球/zonotope 集员机制 | **修正** | 问题 1 的天然几何是 **角扇区 → 半平面约束 → 凸多边形求交 → 直径**；集员文献只提供 bounded-uncertainty / guaranteed feasible set 的理论背景 |
| 5 | "频道切换（1 s × 频道距离）" | **错误，已改** | 题目原文：任意两个频道之间的切换时间为 1 秒。`i ≠ j` 时恒为 1 s |
| 6 | ACC 2012 与 Int. J. Control 2013 并列为两个独立 ANCHOR | **已去重** | 同一研究工作的会议版 / 期刊扩展版，占**一个**槽位 |
| 7 | "CRLB = FIM⁻¹，所以最大化 FIM 与最小化 CRLB 是同一件事" | **已严格化** | `C_CRLB = J⁻¹` 仅在正则条件满足且 FIM 非奇异时成立；矩阵本身不存在"最大化"，必须指定标量最优性准则（A-/D-/E-optimality） |
| 8 | Dehghan 2014 "measurement model 与 B题几乎一一对应" | **已降级表述** | 其 measurement model 是 DRSSI/RSSI，与 B题的 bearing/AOA 不同；可迁移的是**决策框架**，不是测量公式 |
| 9 | 上一轮 correction 判定 2017 A1 "不对应任何已索引记录，疑似 conflation" | **错误，已撤回** | A1 真实存在：Liu, Zhao & Wu 2017, *Journal of Beijing Univ. of Aeronautics and Astronautics* 43(3): 497–505, `10.13700/j.bh.1001-5965.2016.0196`。2014 / 2016 / 2017 是**三个不同工作**。**数据库未召回 ≠ 论文不存在** |

Queries issued in the A-cluster supplement: 10 (4 metadata verification + 6 supplemental
search) — 6 fully effective, 3 partially effective, 1 ineffective (1 zero-return).
Failed: 0. **The final correction pass issued no queries at all**; it is fact-checking
and documentation consistency only.
Not done: PDFs, full text, Crawl4AI, citation snowball, Asta, clusters D/E/F, L2+.

---

## 1. Executive Summary

B 题的数学内核在文献中对应三条研究线：**A 有界误差下的方向定位**、**B 最优观测几何**、
**C 主动感知 / 路径规划**。Round 1 曾判断 A 线与 B/C 在索引文献中"没有接上"——
**该判断是检索假阴性，已撤回**。定向补检在 A 线上找到了一批直接论文，其中一篇
（Isler & Bajcsy 2006）几乎就是问题 1 与问题 2 的通用框架。

**问题 1**（方向观测 + ±1° 硬误差 → 定位区域 → 直径）落在 *bounded-uncertainty
sensing / set-membership localization* 上。这个方向不仅有文献，而且有**比 Round 1
描述得更直接的文献**：

- **Isler & Bajcsy 2006** 给出了一个通用的"有界不确定性传感模型"——测量被表示为
  平面上的**凸多边形子集**，测量之间**通过求交合并**，而**测量不确定性就是交集
  的面积**，并给出传感器选择算法与 2-近似保证。这正是问题 1/2 的结构。
- **Calafiore 2026** 在 UBB 距离测量下刻画"与测量及其误差模型相容的全部点"构成的
  集合，证明它含于若干闭球与**一个多面体**的交，并计算紧的外包围集（盒/椭球）作为
  **保证集值定位估计**。
- **Li et al. 2025**（ICSPS，OpenAlex + Crossref 双库确认）明确处理
  *bounded bearing-only measurements* 下的 set-membership 滤波。
- **Liu & Zhao 2014**（PLANS）在 bearing-only 下用椭球的 **generalization radius**
  作为最优性准则。
- **Liu, Zhao & Wu 2017**（《北京航空航天大学学报》，中文）把 bearing-only +
  unknown-but-bounded + set-membership + 椭球外包围做成了完整工作。**该文本轮未被
  OpenAlex 与 Crossref 召回**，经期刊官方来源确认存在——它是本簇"这条研究线真实
  存在"最直接的证据，也说明中文源是当前的覆盖盲区（见 §7 gap 7）。

**问题 2**（第二观测点选择）依然是最成熟的一条。Zhao–Chen–Lee 用 frame theory
给出最优布站的**充要条件与构造算法**；Yang 等 2013 给出**任意高斯先验**下最大化
更新后 FIM 的放置准则——这正是"已测一次，下一步放哪里"的正确形式；Tang 等 2025
用 A-optimality（min trace CRB）给出含 AOA 的最优几何约束。此外补检新发现
**Fu et al. 2026**（近海 AUV，bearing-only）**解析地求出"最优的下一批观测方位"**，
以及 **Zheng et al. 2023**（Shiyu Zhao 组）把三角几何约束直接并入估计器并证明指数收敛。

**问题 3**（搜索 + 定位 + 清除，目标数未知）本轮有**最重要的新发现**：
Kieffer / Piet-Lahanier 一系的工作（Reynaud 2018 CDC、Reboul 2019 IFAC、
Ibenthal 2020 CDC、Ibenthal 2023 T-RO）在**有界误差**框架下做多目标搜索与跟踪，
维护"已定位目标的状态集"与"**尚未发现目标的状态集**"，并用这两者选择下一步控制量
以最小化下一步的估计不确定性。这正面回答了 Round 1 声称"不存在"的那一类方案。

**最关键的方法论缺口（修正后）**：本轮检索到并纳入核心候选的 **FIM/CRLB-based
placement / planning work 主要采用概率噪声模型，并通常需要给定测量方差**，其中多篇
采用 Gaussian assumption；而题目给的是**硬上下界 ±1°**。需要说明的是，
Fisher information / CRLB **本身并不只适用于 Gaussian model**——但在上述这批
**具体工作**里，噪声假设与题目的纯硬界并不直接等价，把硬界映射成方差仍是一个
必须自行论证的建模决策。
而正因为可行集可以**精确**算出（角扇区 = 半平面约束求交 = 凸多边形），我们可以绕开
这个不匹配：直接以集合尺度（直径 / 面积）作为分布无关的准则——**这件事在
bounded-error 文献里有成熟先例**（Isler & Bajcsy 的面积、CLOSURE 的最小外接球半径、
Liu & Zhao 的 generalization radius），只是**没有人在 B题这一具体几何下做过**。

**下一轮最该深读**：Isler & Bajcsy 2006（问题 1/2 的框架）、Calafiore 2026
（精确可行集与外包围）、Reynaud 2018（问题 3 的集员决策环）、Zhao–Chen–Lee 2013
（最优几何闭式结果）、Yang 2013（带先验的放置）、Dehghan 2014（RF+UAV 单步信息决策）。

---

## 2. Problem A — Bounded-error / Set-based Bearing Localization

> 本节在 Round 1 基础上**重做候选表**。分级标准见 §6。

### 检索观察

- Round 1 的 arXiv 精确短语 `"bearing-only" AND "set-membership"` 返回 **0 条**，
  当时被解读为"交集为空"。补检表明这是**查询方言假阴性**：改用
  `bearing-only set-membership estimation bounded measurements` 后，同一概念返回 8 条，
  其中 3 条直接相关（`2603.04867`、`2604.00561`、`2506.08530`）。
- OpenAlex 的 `bearing` 机械轴承歧义仍然存在（Round 1 已记录），但换成
  `set-membership guaranteed sets target search tracking UAV unknown number of targets`
  这类**不含 bearing 的策略性措辞**后，命中了一整条此前完全遗漏的研究线。
- 由此确立本轮最重要的检索教训：**用词的选择比数据源的覆盖更决定召回**。
  同一批数据库，换一组术语就多出十余篇直接相关论文。
- **A1（2017）的核查本身经历了一次假阴性。** 用标题原文检索 OpenAlex 与 Crossref
  都没有解析出该文，第一轮 correction 据此判定它是两篇论文的 conflation——**该判定
  错误，已撤回**。论文真实存在，发表在中文期刊《北京航空航天大学学报》上，两个数据库
  都不索引它。**"数据库未召回"再次被误当成"论文不存在"**，而且这次发生在中文文献上，
  正是最容易发生这种错误的地方。详见 §2.1。

### 候选论文

字段说明：Measurement type 区分 bearing-only / range-only / RSS / generic；
Noise model 区分 Gaussian / unknown-but-bounded (UBB) / interval / set-membership。

| Title | Year | Measurement | Noise model | Set representation | Core method | Direct relevance to B | Transferable | Non-transferable | Grade | DOI / arXiv |
|---|---|---|---|---|---|---|---|---|---|---|
| The Sensor Selection Problem for Bounded Uncertainty Sensing Models | 2006 | **generic bounded-uncertainty**（含相机） | bounded（测量即凸多边形） | **凸多边形子集** | 测量求交合并；不确定性 = 交集**面积**；传感器选择 2-近似算法 | 问题 1 + 问题 2 的通用框架：求交 + 集合尺度 + 选传感器 | 求交合并语义；集合尺度作目标；"给定可能位置集合而非单点估计"的松弛形式 | 传感器模型是通用多边形，未给角度扇区；无移动/代价模型 | **ANCHOR** | 10.1109/tase.2006.876615 |
| Set-Membership Localization via Range Measurements | 2026 | range-only | **UBB** | 球交 + **多面体**的交，外包围为盒/椭球 | 刻画全部相容点集；凸规划求紧外包围；另给球/椭球内近似 | 问题 1 的最近同构：UBB → 可行集 → 保证集值估计 | 相容集刻画；多面体包含结构；内外近似的凸规划形式 | 测距而非测向；静态锚点；无"选下一个观测点" | **ANCHOR** | arXiv:2603.04867 |
| A Set-Membership Filter for Group Target Tracking Using Bounded Bearing-Only Measurements | 2025 | **bearing-only** | **bounded**（初值/过程/测量噪声均为紧集） | 紧集，逐时刻传播 | 集员滤波；以包含目标状态的集合传播实现跟踪 | 直接的 bounded bearing-only 集员论文；群目标场景 | "把初值、过程噪声、测量噪声统一建模为紧集"的表述 | 动态滤波而非静态几何求交；群目标形状演化不在 B题内 | **ANCHOR** | 10.1109/icsps66615.2025.11347948 |
| A set-membership approach to find and track multiple targets using a fleet of UAVs | 2018 | 探测（集合语义） | **bounded** | 有界集 | 维护"已定位目标状态集" + "**尚未发现目标状态集**"；控制量最小化下一步估计不确定性 | 问题 3 的决策架构：目标数未知 + 搜索 + 定位 | 决策环；未发现目标集的构造与使用；下一步不确定性最小化 | 传感器为探测/可见性模型而非 bearing；UAV 队而非单机器狗；无频道/光学/清除代价 | **ANCHOR** | 10.1109/cdc.2018.8619672 |
| Cooperative guidance of a fleet of UAVs for multi-target discovery and tracking ... set membership approach | 2019 | 探测 | **bounded** | 有界集 | 定义覆盖"已发现 + 尚未发现"目标的统一不确定性准则，驱动轨迹选择 | 问题 3：单一标量准则同时权衡搜索与跟踪 | 统一准则的设计思路；遮挡感知 | 同上一行 | USEFUL (high) | 10.1016/j.ifacol.2019.11.266 |
| Localization of Partially Hidden Moving Targets Using a Fleet of UAVs via Bounded-Error Estimation | 2023 | 可见性 | **bounded** | 分布式集员估计集 | 分布式集员估计 + MPC 降低估计不确定性；逐点 detectability set | 问题 3 的高水平实现参考 | MPC + 集合目标；detectability set（与"信号有效覆盖"同构） | 可见性测量；多机；三维 | USEFUL (high) | 10.1109/tro.2023.3303693 |
| Target search and tracking using a fleet of UAVs in presence of decoys and obstacles | 2020 | 探测 | **bounded** | 有界集 | 不可区分目标 + 诱饵；两个集合驱动分布式控制 | 问题 4 的诱饵/误判类比 | 干扰与真实目标不可区分时的处理 | 同上一行 | USEFUL | 10.1109/cdc42340.2020.9303943 |
| Ellipsoidal set filter combined set-membership and statistics uncertainties for bearing-only maneuvering target tracking | 2014 | **bearing-only** | **UBB + 统计混合** | 椭球 | 以椭球 **generalization radius** 为最优性准则求紧外包围椭球 | bearing-only 下"以集合尺度为准则"的直接先例 | 集合尺度（radius）作最优性准则；两类不确定性并存的处理 | 机动目标动态跟踪；两个固定平台 | USEFUL (high) | 10.1109/plans.2014.6851441 |
| Bearing-only target tracking based on ellipsoidal outer-bounding set-membership estimation | 2017 | **bearing-only** | **UBB** | 椭球（外包围） | 椭球外包围集员估计；机动目标下的递推跟踪 | bearing-only + UBB + set-membership 的**直接且完整**工作；本簇"研究线真实存在"的证据 | bearing-only 下的 UBB 处理；outer-bounding 思想 | 动态机动目标跟踪；椭球表示；**不是**本题的静态角扇区精确多边形求交；中文期刊，无数据库 ID | USEFUL (high) | `10.13700/j.bh.1001-5965.2016.0196`（中文期刊；OpenAlex/Crossref 未索引） |
| Extended Ellipsoidal Outer-Bounding Set-Membership Estimation for Nonlinear Discrete-Time Systems with UBB Disturbances | 2016 | generic | **UBB** | 椭球 | 一阶线性化 + 区间分析界定线性化误差椭球；可行集含更多真值 | 一般性 UBB 外包围方法 | 区间分析界定线性化误差 | **非 bearing-only**，是通用非线性系统 | BACKGROUND | 10.1155/2016/3918797 |
| CLOSURE: Fast Quantification of Pose Uncertainty Sets | 2024 | 关键点/位姿（SE(3)） | **UBB** | 位姿不确定集 + 最小外接测地球 | 证明不确定集 = 多个测地球的交；边界采样 + miniball 求最小外接球（= **最小 worst-case 误差界**），并给出与外包近似的紧度证明 | **直接反驳"diameter 不存在"**：worst-case error 界是既有指标 | 最小外接球 ≈ 可行集直径；内/外近似紧度证书 | SE(3) 位姿、关键点测量，非 2D 测向 | USEFUL (high) | 10.1109/rss.2024.xx.072 / arXiv:2403.09990 |
| Beyond Bounded Noise: Stochastic Set-Membership Estimation for Nonlinear Systems | 2026 | generic | **次高斯（无界支撑，样本协方差有界）** | 有限样本不确定集 | 用样本协方差界构造以高概率包含真值的集合 | 硬界 ↔ 概率假设之间的"中间道路" | 把无界噪声纳入集员框架的严格做法 | 非线性系统参数估计 | BACKGROUND | arXiv:2604.00561 |
| Exact recursive updating of uncertainty sets | 2016 | generic linear | **bounded** | 不确定集（精确，非近似） | 两个定理完整刻画不确定集的演化；精确递推算法 | 增量更新可行集的精确方法（问题 1/2/3 的在线更新） | 精确（而非椭球近似）递推更新 | 线性系统；无几何语义 | USEFUL | arXiv:1612.04918 |
| The Invariant Zonotopic Set-Membership Filter for State Estimation on Groups | 2025 | generic | **UBB** | **zonotope（李群上）** | 不变滤波 + zonotope；F-radius 优化增益；以**平均区间面积**为指标 | zonotope 用于 UBB 现代实例；集合面积作为报告指标 | F-radius / 区间面积作为集合尺度指标 | 李群状态空间；动态滤波 | BACKGROUND | arXiv:2506.08530 |
| Recursive state estimation for a set-membership description of uncertainty | 1971 | generic | **UBB** | 椭球 | 递归集员滤波；能量约束→椭球，瞬时约束→包围椭球 | 集员估计的奠基形式 | "测量 + 有界误差 → 相容状态集" | 动态递推机制 B题不需要 | BACKGROUND | 10.1109/TAC.1971.1099674 |
| Optimal estimation theory for dynamic systems with set membership uncertainty | 1991 | generic | **UBB** | 可行集 | 集员估计的最优性理论 | "最小化可行集大小"作为规范最优性准则 | 指标选择的理论背书 | 动态系统 | BACKGROUND | 10.1016/0005-1098(91)90134-N |
| A Dynamic Event-Triggered Transmission Scheme for Distributed Set-Membership Estimation | 2017 | generic | **UBB** | 包围椭球 | 分布式集员估计；包围椭球上的递归凸优化 | "保证包含真值"性质 | 保证包含的形式化 | 传感器网络传输调度 | BACKGROUND | 10.1109/TCYB.2017.2769722 |
| Ellipsoidal state-bounding-based set-membership estimation for linear system with UBB disturbances | 2016 | generic linear | **UBB** | 椭球 | 预测-校正集员递推；**最小化可行椭球体积** | 收缩可行集体积这一目标 | 体积作集合尺度指标 | 线性动态系统 | BACKGROUND | 10.1049/iet-cta.2015.0654 |
| Improved set-membership estimation approach based on zonotopes and ellipsoids | 2014 | generic | **UBB** | zonotope + 椭球 | zonotope→椭球混合；P-radius 切换准则 | zonotope 作为一种有界集表示的背景 | 见下方"关于 zonotope 的更正" | 动态系统；且**不**支持角扇区精确求交 | BACKGROUND | 10.1109/ECC.2014.6862412 |
| Distributed Bearing-based Formation Control and Network Localization with Exogenous Disturbances | 2020 | **bearing** | bounded disturbance | 定位误差的界集 | 鲁棒稳定性；方向测量定位误差的显式上界集 | 少数把方向测量与显式有界误差集耦合的工作 | 误差上界集的构造 | 编队控制框架 | USEFUL | arXiv:2007.07458 |
| Target localization from bearings-only observations | 1997 | **bearings-only** | **非概率（不预设随机或系统误差）** | — | 不预设误差分布的估计方法；可观测性分析 | 罕见的非贝叶斯 bearings-only 估计 | "不预设误差分布"的立场 | 无集合表示；无几何求交 | BACKGROUND | 10.1109/7.570703 |
| Networked pointing system: Bearing-only target localization and pointing control | 2025 | **bearing-only** | — | — | 方向估计 + 指向控制；可定位性条件 | 最小可定位条件（两智能体与目标不共线），可作问题 2 候选区域的合法性下界 | 可定位性条件 | 控制律 | USEFUL | arXiv:2506.18460 |
| The Algorithm of Group Target Tracking Based on Bearing-only Measurements | 2024 | **bearing-only** | — | — | 群目标跟踪算法 | 中文控制界的相邻工作（CCC） | — | 群目标跟踪 | BACKGROUND | 10.23919/ccc63176.2024.10661907 |
| Set-membership estimation for linear time-varying descriptor systems | 2020 | generic | UBB | 可行集 | 描述子系统集员估计 | 几何不可迁移 | — | 描述子系统 | DROP | 10.1016/j.automatica.2020.108867 |
| H∞-optimal Interval Observer Synthesis via Mixed-Monotone Decompositions | 2022 | generic | **interval** | 区间（盒子） | 区间观测器，构造即保证包含 | 区间/盒子表示概念 | 区间表示 | LMI/SDP 机制 | BACKGROUND | arXiv:2203.07430 |
| Distributed Resilient Interval Observer Synthesis | 2024 | generic | **interval** | 区间 | 分布式区间观测器，ℓ1 误差界最小化 | "最小化误差界" | 误差界最小化 | 同上 | BACKGROUND | arXiv:2401.15511 |

### 关于 2017 A1 论文（前期误判的更正，对应更正表 #9）

第一轮 correction 曾判定 brief 给出的 A1 标题"不对应任何已索引记录"，并进一步推断
它是两篇论文的 **conflation**。**该推断是错的，现撤回。**

三个工作彼此不同，只是同一课题组的相邻研究：

| 年 | 论文 | 测量 | 作者 | 性质 |
|---|---|---|---|---|
| 2014 | *Ellipsoidal set filter combined set-membership and statistics uncertainties for bearing-only maneuvering target tracking*（PLANS 2014，`10.1109/plans.2014.6851441`） | bearing-only | Liu & Zhao | 真实的 bearing-only 工作，两类不确定性并存 |
| 2016 | *Extended Ellipsoidal Outer-Bounding Set-Membership Estimation for Nonlinear Discrete-Time Systems with Unknown-but-Bounded Disturbances*（IJDSN 2016，`10.1155/2016/3918797`） | **非 bearing-only** | Liu, Zhao & Wu | 通用非线性系统的 UBB 外包围 |
| 2017 | *Bearing-only target tracking based on ellipsoidal outer-bounding set-membership estimation*（**《北京航空航天大学学报》** 43(3): 497–505，`10.13700/j.bh.1001-5965.2016.0196`） | bearing-only | Liu, Zhao & Wu | **本轮被误判为不存在的那一篇**；经期刊官方来源确认存在 |

**可迁移**：bearing-only、unknown-but-bounded noise、set-membership、椭球外包围、
集合尺度 / 外包围（outer-bounding）思想。

**不可直接迁移**：动态机动目标跟踪；椭球外包围；**不是**本题的静态角扇区精确求交。

> 它的价值是证明 **bearing-only + unknown-but-bounded + set-membership 是真实存在的
> 直接研究线**，**不是**证明 B题问题 1 必须用椭球。

**为什么它不进 ANCHOR、也不进 Tier 1 / Tier 2**：判据是"是否直接改变我们对 B题模型、
算法、目标函数或关键证明的设计"。该文解决的是动态机动目标的递推滤波，而问题 1 是静态
几何求交，因此它提供的是**存在性证据**，不是可直接搬运的设计。这不是遗漏，是判据的
结果；若后续确实需要"以椭球而非多边形做外包围"的对照方案，再补读不迟。

**Provenance**：本轮**没有**为它伪造任何 OpenAlex ID、Crossref ID 或 DOI 之外的东西。
它以 `verified_external_record` 形式记录在 `raw/round1_correction_A.json`，
`verification_source = official journal page`；需要说明的是，**该核实发生在本次检索
运行之外**（由用户提供的 correction brief 转述），而本次运行的数据库查询**没能**召回它。

### 关于 zonotope 的更正（对应更正表 #3）

Round 1 曾写"zonotope 对 Minkowski 和与求交封闭——累积角扇区求交的天然代数"。
**这是错的。** 正确的表述是：

```
普通 zonotope：
  - 对 affine / linear transformation 封闭
  - 对 Minkowski sum 封闭
  - 一般 不 对 intersection 封闭
```

若需精确处理交集，通常需要 `constrained zonotope`、`zonotope bundle`，
或退而求其次使用 `outer approximation` 等扩展或近似形式。

因此 **Ben Chabane et al. 2014 不再作为 ANCHOR**。它作为
bounded-set representation / set-membership estimation / outer approximation 的
背景文献保留，等级 **BACKGROUND**。

### 本节结论（修正后）

- **有界误差 × 方向定位不是两个互不相交的社区。** 该交集有多篇直接论文
  （Isler & Bajcsy 2006；Calafiore 2026；Li et al. 2025；Liu & Zhao 2014；
  Liu, Zhao & Wu 2017）。
- **本轮仍未找到与 B题完全同构的论文**：即
  "±1° 有界角度误差 → 多个角扇区精确求交 → 凸多边形 → 计算欧氏直径"。
  最接近的是 Isler & Bajcsy 2006（凸多边形求交 + 面积，但测量模型是通用多边形）
  与 Calafiore 2026（UBB + 多面体 + 保证集值估计，但测量是测距）。
- **不能声称 diameter 在文献中不存在。** 集合尺度是既有指标族：
  面积（Isler & Bajcsy）、最小外接球半径 / worst-case 误差界（CLOSURE）、
  generalization radius（Liu & Zhao）、体积（Liu et al. 2016）、
  F-radius 与区间面积（InZSMF 2025）。缺的是**在本题几何下的具体算法与结论**，
  不是这个概念本身。

---

## 3. Problem B — Optimal observation geometry

### 候选论文

| Title | Year | Core method | Scalar optimality criterion | Key geometric result | Direct relevance to B | Grade | DOI / arXiv |
|---|---|---|---|---|---|---|---|
| Optimal sensor placement for target localisation and tracking in 2D and 3D | 2013 | frame theory 统一 bearing-only / range-only / RSS | FIM 型（原文给出最优性的充要条件） | 2D/3D 最优放置的**充要条件**；regular/irregular 两类；梯度控制律可构造 | 问题 2 的数学内核：闭式最优几何 | **ANCHOR** | 10.1080/00207179.2013.792606（预印本 arXiv:1210.7397） |
| Optimal Placement of Heterogeneous Sensors for Targets with Gaussian Priors | 2013 | 从**任意高斯先验**出发最大化**更新后** FIM；异构传感器含 bearing-only；多步 | D-optimality（det FIM） | 任意先验下的最优放置条件 | **与问题 2 结构同构**：测一次 → 先验 → 选第二测点 | **ANCHOR** | 10.1109/TAES.2013.6558009 |
| Optimal Sensor Placement Using Combinations of Hybrid Measurements | 2025 | TDOA/RSS/**AOA**/TOA 组合的 CRB | **A-optimality（min trace CRB）** | 各测量类型的最优几何约束，含 AOA 的显式结果 | "最优夹角"的直接文献来源 | **ANCHOR** | arXiv:2504.03769 |
| Optimization of observer trajectories for bearings-only target localization | 1999 | 最优控制（微分包含） | **D-optimality（max det FIM）**，带状态约束 | 最优观测者轨迹；机动提升可观测性 | 横跨 B/C：同一准则的动态版 | **ANCHOR** | 10.1109/7.784059 |
| Optimal Spatial-Temporal Triangulation for Bearing-Only Cooperative Motion Estimation | 2023 | 分布式递归最小二乘，并入**三角几何约束** | — | 指数收敛性证明；精度与收敛速度优于 DKF | 与 Zhao–Chen–Lee 同组（Shiyu Zhao）；补上构造性估计器 | USEFUL (high) | arXiv:2310.15846 |
| Improving D-Optimal Sensor Placement for Bearing-Only Localization via Maximum-Entropy Reweighting | 2026 | KL 散度粒子重加权 + 重加权 FIM 上的最优放置 | **D-optimality（det FIM）** | 两层解耦：重加权跨模态通用，放置专属方向几何 | 放置准则与 Zhao/Yang 大量重叠；其特色（跨模态重加权）B题用不上 | USEFUL (high) | arXiv:2605.11116 |
| Optimal Sensor Placement for Source Localization: A Unified ADMM Approach | 2021 | CRLB 统一 + ADMM/MM 求解器 | A / D / E-最优性可切换 | 统一求解器，可处理相关噪声 | **优化器模板**；测量类型为 TOA/TDOA/RSS | USEFUL | arXiv:2109.03639 |
| Optimal Sensor Placement for Multiple Target Positioning with Range-Only Measurements | 2013 | 传感器位置上的凸优化 | **最大化跨目标的 log det FIM 凸组合** | 最优构型显式依赖约束、目标位置与先验不确定度 | 多目标准则形式 → 问题 3 | USEFUL | 10.3390/s130810674 |
| Multisensor-Multitarget Bearing-Only Sensor Registration | 2016 | 融合节点上的 ML 偏差估计 | 推导 CRLB | 偏差仅有机动下可辨识 | bearing-only 的 ML 估计 | USEFUL | arXiv:1603.03450 |
| Relationship Between Geometric Translations and TLS Estimation Bias in Bearings-Only Target Localization | 2008 | TLS 估计偏差分析 | — | 估计偏差依赖**坐标原点位置** | 题目把原点固定在圆域中心——真实的设计注意事项 | BACKGROUND | 10.1109/TSP.2007.909052 |
| Fisher-Information-Based Sensor Placement for Structural Digital Twins | 2026 | 伴随法算 FIM 乘积 | **D-optimality（log det）** | 区分 detectability 与 localizability | 仅概念层面（结构力学） | BACKGROUND | arXiv:2602.02981 |
| Outlier Detection and Optimal Anchor Placement for 3D Underwater Optical WSN | 2018 | 半二次最小化 | **D-optimality**（组合 FIM） | 满足 D-最优性的锚点布置 | 方法桥梁 | BACKGROUND | arXiv:1810.03110 |

### 去重说明（对应更正表 #6）

`Optimal placement of bearing-only sensors for target localization`（ACC 2012，
`10.1109/ACC.2012.6314884`）与 `Optimal sensor placement for target localisation and
tracking in 2D and 3D`（Int. J. Control 2013，`10.1080/00207179.2013.792606`）
属**同一研究工作的会议版与期刊扩展版**。Round 1 曾把它们并列为两个独立 ANCHOR。

正确处理：**深读集合中只占一个主槽位**，以期刊版为主条目：

```
Zhao, Chen & Lee — Optimal sensor placement for target localisation and
tracking in 2D and 3D (Int. J. Control 2013)
  Earlier conference version:
  Optimal placement of bearing-only sensors for target localization
  (ACC 2012, 10.1109/ACC.2012.6314884)
```

会议版若含期刊版缺失的构造细节，仍可在深读时一并查阅，但**不重复计入 ANCHOR 数量**。

### FIM / CRLB / GDOP 与标量最优性准则（对应更正表 #7）

Round 1 曾写"CRLB = FIM⁻¹，所以最大化 FIM 与最小化 CRLB 是同一件事"。
该表述过于宽泛，现严格化如下。

在满足常规正则条件且 FIM 非奇异时，Cramér–Rao 下界为

```math
C_{CRLB} = J^{-1}
```

但 **J 是矩阵，矩阵本身没有"最大化"这个操作**。要把它变成可优化的问题，
必须指定一个**标量最优性准则**：

```math
\text{D-optimality:} \quad \max \det(J) \iff \min \det(J^{-1})
```

```math
\text{A-optimality:} \quad \min \operatorname{trace}(J^{-1})
```

```math
\text{E-optimality:} \quad \max \lambda_{\min}(J)
```

几何含义：

- **D-optimality** 最小化误差椭球的**体积**（det(CRB) 最小）。
- **A-optimality** 最小化误差椭球**半轴平方和**，即 trace(CRB)。
- **E-optimality** 最小化误差椭球的**最大半轴**。

三者**不等价**，会给出不同的最优布站。本报告此后所有"最大化 FIM / 最小化 CRLB"
的措辞都替换为带准则名的表述。

另外必须明确一点，以免把上面这套工具误用成"题目可以当高斯用"的许可：
**Fisher information / CRLB 本身并不要求 Gaussian 噪声**（在正则条件下对一般参数化
分布族成立）。真正受限的是**本轮纳入核心候选的这批** bearing-only 布站 / 轨迹规划工作：
它们**主要采用概率噪声模型，并通常需要给定测量方差**，其中多篇明确采用 Gaussian
assumption。因此它们不能直接替代题目给出的 **±1° hard bound model**；
"FIM 在数学上不限于高斯"与"本题的硬界可以直接当方差用"是两件事。

关于 **GDOP**：GDOP 是 CRLB 的归一化标量形式，其数值依赖测量精度是否已归一、
以及参考哪一类误差分量。本报告不使用未定义归一化条件的 GDOP 数值；
若后续使用，必须同时给出定义与归一化约定。补检仍未命中以 GDOP 命名的 B 簇论文。

### 关于最优角度

在 2D、两个测点、目标固定且距离固定的设定下，最优构型由 frame theory 的充要条件
给出；直观结果是两视线的**交会角趋近 90°**（交会角正弦最大）。Xiao 2026 把这一点
直接写成 "intersection angle sine term" 加入目标函数，Tang 2025 的 AOA 几何约束
与之互为印证。补检新增 **Fu et al. 2026**（arXiv:2410.18669），它更进一步：
先建立**依赖于方位数据的跟踪误差界**，再**解析地**求出使跟踪不确定性下降的
**最优目标方位**——这正是问题 2 的提问方式。

---

## 4. Problem C — Active sensing / path planning

### 候选论文

| Title | Year | Core method | Planning objective | Uncertainty metric | Horizon | Direct relevance to B | Grade | DOI / arXiv |
|---|---|---|---|---|---|---|---|---|
| Optimization of observer trajectories for bearings-only target localization | 1999 | 最优控制 / 微分包含 | max det(FIM)，带状态约束 | FIM det | 轨迹 | 问题 2→3 的桥梁 | **ANCHOR** | 10.1109/7.784059 |
| Optimal path planning for DRSSI based localization of an RF source by multiple UAVs | 2014 | EKF + 候选航点上的局部 CRLB | 在下一候选航点上 max det(CRLB⁻¹) | CRLB / 估计不确定区域 | **单步前瞻**（离散候选集） | 决策架构与问题 3 高度相似（**但测量模型不同，见下**） | **ANCHOR** | 10.1109/IROM.2014.6990961 |
| Path planning for localization of an RF source by multiple UAVs on the Crammer-Rao Lower Bound | 2013 | 局部 CRLB 上的最速下降 + 空间离散 | min CRLB 标准差 | CRLB | 单步 | 上篇的前身，同一课题组 | USEFUL | 10.1109/IROM.2013.6510083 |
| A set-membership approach to find and track multiple targets using a fleet of UAVs | 2018 | 有界集上的集员估计 + 控制量优化 | **最小化下一步估计不确定性** | **集合尺度（非概率）** | 单步（滚动） | **问题 3 的最近架构**：目标数未知 + 搜索 + 跟踪 | **ANCHOR** | 10.1109/cdc.2018.8619672 |
| Cooperative guidance ... set membership approach | 2019 | 统一不确定性准则驱动轨迹 | 覆盖"已发现 + 未发现"目标的准则 | 集合尺度 | 单步 | 搜索-跟踪权衡的显式准则 | USEFUL (high) | 10.1016/j.ifacol.2019.11.266 |
| Localization of Partially Hidden Moving Targets ... Bounded-Error Estimation | 2023 | 分布式集员估计 + MPC | 降低估计不确定性 | 集合尺度 | MPC 滚动时域 | 问题 3 高水平参考 | USEFUL (high) | 10.1109/tro.2023.3303693 |
| Trajectory Optimization for Unknown Maneuvering Target Tracking with Bearing-only Measurements | 2024 | GP 学习 + 伪线性变换；**解析求最优目标方位** | 最小化跟踪不确定性 | 概率型方位数据依赖界 | 轨迹 | bearing-only；解析的"下一观测方位" = 问题 2 | **ANCHOR** | arXiv:2410.18669 |
| GyroCopter: Differential Bearing Measuring Trajectory Planner for Tracking and Localizing RF Sources | 2024 | 飞行动力学产生伪方位测量；推导最优旋转速度 | 方位获取效率 | — | 轨迹 | 唯一处理**多 RF 源**的方位获取规划 + 实地验证 | **ANCHOR** | arXiv:2410.13081 |
| Trajectory Optimization in Single and Dual-UAV Bearing-Only Target Localization | 2026 | 谱加权 FIM 目标 + 带运动约束的 PSO | 谱加权 FIM；双机加交会角正弦项 | FIM（谱） | 轨迹 | 最新 bearing-only 轨迹优化 | **ANCHOR** | arXiv:2606.09188 |
| A Bearing-Strength Method for Motion Estimation of Unknown Energy Emitters | 2026 | 方位 + 接收强度融合 | 可观测性 | 可观测性条件 | 运动策略 | 指出 bearing-only 可观测性**要求横向运动**；题目的测向机正是"方位+场强" | **ANCHOR** | arXiv:2607.12515 |
| RF Source Seeking using Frequency Measurements | 2018 | 多普勒频率反馈 + 方位扰动 | 逼近辐射源 | — | 连续自适应 | 圆周运动消解方向二义性 | USEFUL | arXiv:1803.02494 |
| Adaptive Informative Path Planning with Multimodal Sensing | 2020 | POMDP + POMCP | 信息增益 vs 能量，**多传感器间选择** | belief 熵 | 滚动时域 | POMDP 可承载"切换频道"的离散动作与代价 | USEFUL | arXiv:2003.09746 |
| Multi-UAV Active Sensing with Information Gain-based Planning and Belief Fusion | 2026 | 因子图 belief map + IGbIPP | 信息增益 | 熵 | 滚动时域 | 通用 IPP 模板 | USEFUL | arXiv:2606.10986 |
| Homotopic information gain for sparse active target tracking | 2026 | 同伦信息增益（度量下界） | 同伦信息增益 | 信息增益 | 轨迹 | 稀疏观测下的信息增益度量 | USEFUL | arXiv:2602.17926 |
| Bearings-only target localization for an acoustical unattended ground sensor network | 2001 | 准 ML + 方位关联 | — | — | 静态，多目标 | 多源**数据关联** | USEFUL | 10.1117/12.441279 |
| Measurement Testbed for Radar and Emitter Localization of UAV at 3.75 GHz | 2022 | 测量试验台 | — | — | 硬件 | 背景 | BACKGROUND | arXiv:2210.07168 |
| Multi-Robot IPP / Active Markov ITPP / Online IPP for 3D Surface | 2011–2021 | GP 上的熵与互信息 IPP | 熵、互信息 | GP 后验 | 轨迹 | 通用 IPP 背景，非 RF | BACKGROUND | arXiv:1302.0723 / 1101.5632 / 2103.09556 |

### Dehghan 2014 的适用范围（对应更正表 #8）

保留该文献，它仍是高价值结果。但**不再声称** "exact structural match" 或
"几乎一一对应 B题 measurement model"。

其 measurement model 是 **DRSSI / RSSI**（差分接收信号强度），
而 B题的核心测量是 **bearing / AOA，带 ±1° 硬误差**。准确表述是：

```
其 sequential decision architecture 与 B题高度相似：

    当前估计
      → 评价候选下一航点
      → 选择信息收益更大的观测位置
      → 新测量
      → 更新估计

但其 measurement model 与 B题不同，
因此只能迁移"决策框架 / path-planning structure"，
不能直接搬用全部测量公式。
```

### 失败查询记录（保留）

`UAV radio source localization path planning trajectory optimization` 返回的 6 条
**全部**是通用 UAV 轨迹规划（自主着陆、系绳 UGV-UAV、AoI 数据采集、δ-spaces），
无一条涉及辐射源。改用 `radio emitter geolocation UAV search bearing measurements`
后命中率大幅提升——"UAV + trajectory optimization" 会淹没 "RF source" 这一语义。

### 规划目标统计

- **D-optimality（max det FIM / min det CRLB）**：Oshman 1999、Dehghan 2014
- **A-optimality（min trace CRLB）**：Tang 2025、Sahu 2021
- **posterior entropy / 信息增益**：Habibi 2026、Choudhury 2020、Cao 2013、
  Wakulicz 2026
- **集合尺度（非概率）**：Reynaud 2018、Reboul 2019、Ibenthal 2020/2023 ——
  **本轮新增，且是与 B题误差模型最匹配的一类**
- **未出现**：首次发现概率（本簇未检索到——属 D 簇范畴）

---

## 5. Cross-cluster synthesis

### 统一建模链

```
B题的观测模型：bearing measurement + hard angular bound ±1°
        ↓
每次测量形成一个 guaranteed angular sector
   （角扇区 = 顶点 + 两条射线 = 两个线性半平面约束）
        ↓
多个 sector 精确求交（convex polygon intersection / polygon clipping）
        ↓
convex feasible polygon（定位区域）
        ↓
polygon diameter / area / 其他集合尺度
        ↓
选择下一观测点
        ↓
两类可能策略：

   A. 直接 worst-case / feasible-set reduction
      最小化下一步后可能定位区域的最坏直径

   B. 使用概率近似后借用
      FIM / CRLB / A-opt / D-opt
      作为 surrogate benchmark
        ↓
移动 / 新观测
        ↓
更新 feasible set
```

### 已有文献直接支持

| 环节 | 文献支持 | 具体来源 |
|---|---|---|
| unknown-but-bounded / set-membership philosophy | ✅ 成熟 | Bertsekas 1971、Belfonte 1991、Liu et al. 2016、Li et al. 2025、**Liu, Zhao & Wu 2017（中文期刊）** |
| **有界不确定性 → 凸多边形测量子集 → 求交合并 → 集合尺度** | ✅ **成熟（本轮新确认）** | **Isler & Bajcsy 2006** |
| UBB → 相容集 → 多面体 → 保证集值估计 | ✅ 有直接论文 | Calafiore 2026 |
| **集合尺度（worst-case 误差界 / 最小外接球）作精度指标** | ✅ **有先例** | CLOSURE 2024、Liu & Zhao 2014、InZSMF 2025 |
| bearing-only optimal geometry | ✅ 成熟 | Zhao–Chen–Lee 2013、Tang 2025、Zheng 2023 |
| FIM / CRLB 观测几何 | ✅ 成熟（须带标量准则） | Zhao 2013、Oshman 1999、Yang 2013、Sahu 2021 |
| 解析地求"下一个最优观测方位" | ✅ 有直接论文 | Fu et al. 2026（arXiv:2410.18669） |
| active sensing / sequential next-waypoint planning | ✅ 成熟 | Dehghan 2014、Xiao 2026、Choudhury 2020 |
| **有界误差下的多目标搜索 + 目标数未知** | ✅ **有直接论文（本轮新确认）** | Reynaud 2018、Reboul 2019、Ibenthal 2020/2023 |
| 不确定集的精确增量递推 | ✅ 有直接论文 | Hill et al. 2016（arXiv:1612.04918） |

### 需要本题自行设计

1. **±1° 角扇区的精确几何求交**在 B题具体设定下的算法细节：扇区表示、
   半平面求交、增量式更新、顶点集维护、退化处理（近共线、扇区不交、单点退化）。
   *（通用框架有 Isler & Bajcsy 2006；本题几何下的具体算法未见。）*
2. **polygon diameter 算法**及其两个特例：凸多边形直径（旋转卡壳 / 凸包），以及
   两测点下四边形 6 对顶点距离的闭式比较；以及"以直径为直径的圆能否覆盖此定位
   区域"这一判断题的证明。*（直径作为集合尺度有先例，本题的具体构造未见。）*
3. **基于 hard-bound feasible polygon 的 second-point strategy**：把"使求交后可行
   多边形直径最小"直接作为候选点评分函数，并在候选区域上求解。
   *（Reynaud 2018 / Reboul 2019 的最小化集合不确定性准则形式相同，但测量模型
   与几何不同。）*
4. **搜索、频道检测、定位和清除的联合时间优化**：离散频道（任意两频道切换恒 1 s）、
   固定 5 s 检测、20 m 内 3 s 光学、2 s 清除、**≤5 m 且位于有效覆盖角内时可跳过
   示向度检测、直接 3 s 光学定位 + 2 s 清除**、5 m/s 移动、
   程序运行 20 分钟上限（且受 25 分钟测试窗口约束，以较早到达者为准）、
   目标数未知 10–16。*检索到的规划工作都没有这个代价模型。*

**表述纪律**：以上四项一律写作"本次受控检索尚未找到完全同构的现成方案"，
**不写作"文献完全没有"**。

---

## 6. ANCHOR 与 Deep Reading Set

### ANCHOR 判定标准

ANCHOR 必须满足：**直接改变我们对 B题模型、算法、目标函数或关键证明的设计**。
不因为 citation count 高、领域经典、或概念相邻就标为 ANCHOR。

### ANCHOR（12 篇）

| # | 论文 | Cluster | 它改变了什么 |
|---|---|---|---|
| A1 | Isler & Bajcsy 2006, *The Sensor Selection Problem for Bounded Uncertainty Sensing Models* | A | 问题 1/2 的框架：凸多边形测量子集求交 + 集合尺度 + 选观测 |
| A2 | Calafiore 2026, *Set-Membership Localization via Range Measurements* | A | 精确可行集的外包围与保证集值估计 |
| A3 | Li et al. 2025, *A Set-Membership Filter for Group Target Tracking Using Bounded Bearing-Only Measurements* | A | bounded bearing-only 集员的存在性锚点 |
| A4 | Reynaud et al. 2018, *A set-membership approach to find and track multiple targets using a fleet of UAVs* | A/C | 问题 3 的决策环：目标数未知 + 未发现目标集 |
| B1 | Zhao, Chen & Lee 2013, *Optimal sensor placement for target localisation and tracking in 2D and 3D*（含 ACC 2012 会议版） | B | 最优几何的充要条件与构造算法 |
| B2 | Yang et al. 2013, *Optimal Placement of Heterogeneous Sensors for Targets with Gaussian Priors* | B | "已有先验时下一步放哪里"的正确形式 |
| B3 | Tang et al. 2025, *Optimal Sensor Placement Using Combinations of Hybrid Measurements* | B | A-optimality 下 AOA 的显式最优几何 |
| B4 | Oshman & Davidson 1999, *Optimization of observer trajectories for bearings-only target localization* | B/C | 轨迹级 det(FIM) 的经典范式 |
| C1 | Dehghan et al. 2014, *Optimal path planning for DRSSI based localization of an RF source by multiple UAVs* | C | RF+UAV 单步前瞻决策架构（**仅架构**） |
| C2 | Chen et al. 2024, *GyroCopter: Differential Bearing Measuring Trajectory Planner* | C | 多 RF 源的方位获取 + 实地验证 |
| C3 | Xiao et al. 2026, *Trajectory Optimization in Single and Dual-UAV Bearing-Only Target Localization* | C | 交会角正弦项的工程化写法 |
| C4 | Fu et al. 2024/2026, *Trajectory Optimization for Unknown Maneuvering Target Tracking with Bearing-only Measurements* | C | 解析求"下一个最优观测方位" |

**Round 1 → 本次修订的 ANCHOR 变化**：

- **新增 4 篇**（A1–A4），全部来自 A 簇补检。
- **去重 1 组**：ACC 2012 并入 B1，不再单独计数。
- **降级 2 篇**：Ben Chabane 2014 → BACKGROUND（zonotope 不对交集封闭，
  不能支持角扇区求交）；Bhattacharya 2026 → USEFUL (high)（其放置准则与
  B1/B2 大量重叠，特色是跨模态重加权，B题用不上）。

### Deep Reading Set（10 篇）

**Tier 1 — 必须立刻深读（6 篇）**

| # | 论文 | 为什么要全文 | 从正文要提取什么 |
|---|---|---|---|
| 1 | **Isler & Bajcsy 2006** (`10.1109/tase.2006.876615`) | 问题 1 与问题 2 的通用框架就在正文里，摘要只说了结论 | 传感器模型的形式化；求交合并的算法与数据结构；面积指标的用法；2-近似保证的证明思路；"给定可能位置集合而非单点估计"这一松弛的完整处理 |
| 2 | **Calafiore 2026** (arXiv:2603.04867) | 问题 1 的最近同构；外包围与内近似的凸规划形式直接可用 | 相容集的定义式；多面体包含性的证明；取紧外包围盒/椭球的凸程序；内近似的球/椭球形式；与 SDP 松弛路线的对比 |
| 3 | **Reynaud et al. 2018** (`10.1109/cdc.2018.8619672`) | 问题 3 的目标数未知 + 搜索 + 定位决策环 | 两个集合（已定位 / 未发现）的递推更新式；控制目标函数的构造；"下一步不确定性"如何度量与优化；算法伪代码与计算复杂度 |
| 4 | **Zhao, Chen & Lee 2013** (`10.1080/00207179.2013.792606`) | 问题 2 的数学内核全在充要条件与构造算法里 | 最优放置的充要条件；regular / irregular 两类的定义；显式构造算法；梯度控制律；统一 bearing / range / RSS 的 frame 表述 |
| 5 | **Yang et al. 2013** (`10.1109/TAES.2013.6558009`) | 唯一"已有一次测量/先验，下一次放哪里"的现成形式化 | 更新后 FIM 的表达式；任意高斯先验如何进入准则；多步顺序放置的递推；异构传感器的处理 |
| 6 | **Dehghan et al. 2014** (`10.1109/IROM.2014.6990961`) | 问题 3 决策环最接近的实现 | 候选航点的生成方式；局部 CRLB 的评价方式；单步前瞻的完整流程；**其 DRSSI 测量模型与 B题的差异点** |

**Tier 2 — 有时间再读（4 篇）**

| # | 论文 | 为什么需要 | 提取重点 |
|---|---|---|---|
| 7 | **Li et al. 2025** (`10.1109/icsps66615.2025.11347948`) | 确认 bounded bearing-only 集员的具体构造 | 紧集如何建模；集合传播的近似阶；群目标扩散情形 |
| 8 | **Tang et al. 2025** (arXiv:2504.03769) | 校准我们算出的"最优夹角"是否与文献一致 | AOA 的 A-optimality 显式几何约束；混合测量下的比较 |
| 9 | **Oshman & Davidson 1999** (`10.1109/7.784059`) | 轨迹级 det(FIM) 的经典范式 | 微分包含形式；带状态约束的最优控制解法；可观测性与机动的结论 |
| 10 | **Xiao et al. 2026** (arXiv:2606.09188) | 交会角项如何进入目标函数 | 谱加权 FIM 的定义；双机交会角正弦项；PSO 的约束处理 |

*（Round 1 深读集中的 Ben Chabane 2014 已移出——见更正表 #3。#6 GyroCopter 与
#4 Fu et al. 降为备用：前者是多源方位获取，后者与 Tier 1 #4 部分重叠。）*

---

## 7. Search Gaps

只列本轮**真实存在**的缺口。所有条目一律表述为检索观察，不表述为文献不存在。

1. **与 B题完全同构的几何未检索到。** 即
   "±1° 有界角误差 → 多角扇区精确求交 → 凸多边形 → 欧氏直径"。
   最接近的是 Isler & Bajcsy 2006（凸多边形求交 + 面积）与 Calafiore 2026
   （UBB + 多面体 + 保证集值估计）。**这是应用层面的空白，不是框架层面的空白。**
2. **"直径"作为具体算法未检索到**，但**作为概念有大量先例**（面积、最小外接球
   半径、generalization radius、体积、F-radius、区间面积）。问题 1 要求直径，
   需要我们给出凸多边形的直径算法与覆盖判定。参见更正表 #2。
3. **硬界 → 方差的映射无文献背书。** 本轮检索到并纳入核心候选的 FIM/CRLB-based
   placement / planning work **主要采用概率噪声模型，并通常需要给定测量方差**，
   其中多篇采用 Gaussian assumption；题目给的是 ±1° 硬上下界。需注意
   Fisher information 本身并不只适用于 Gaussian model，受限的是**这批具体工作**的
   噪声假设。因此它们不能直接替代题目的 ±1° hard bound model——
   "±1° 硬界"与"Gaussian variance"之间没有无需额外建模假设的等价关系。补检发现
   Brändle et al. 2026（arXiv:2604.00561）为"无界噪声下的集员估计"给出了严格处理，
   可作为方法论中转，但仍不直接回答"如何把 ±1° 硬界变成方差"。
4. **B题的代价结构无文献建模。** 离散频道（任意两频道切换恒 **1 s**）、固定 5 s
   检测、20 m 内 3 s 光学、2 s 清除、**≤5 m 且位于有效覆盖角内时跳过示向度检测、
   直接 3 s 光学定位 + 2 s 清除**、5 m/s 移动、
   程序运行 20 分钟上限（受 25 分钟测试窗口约束）、目标数未知 10–16。
   最接近的是 POMDP 多模态传感（Choudhury 2020），代价模型不同。
5. **Semantic Scholar 补检返回空。** 查询
   `bearing-only target tracking ellipsoidal outer-bounding set-membership estimation`
   返回空数组（非报错）。**可能是速率限制伪影，不作为该文献不存在的证据。**
   本任务的 A1 核查因此只依赖 OpenAlex 与 Crossref——**而这两个数据库最终也没能
   召回 A1；A1 的存在是靠期刊官方来源确认的（见 §2.1）。这是"零返回 ≠ 不存在"
   在本轮最有力的一次实证，而且它推翻的是我们自己的一个正面断言，不是一条缺失记录。**
6. **GDOP 术语仍未命中 B 簇论文。** 可能是 OpenAlex 对缩写术语的检索弱点，
   不代表文献不存在。
7. **中文文献仍未检索——而且已被证明是真实缺口。** B 题是中文学科竞赛题，
   "交会定位""示向度""测向"等术语的文献主要在 CNKI/万方，arXiv 与 OpenAlex 均不索引。
   现在有了直接证据而不只是推测：**2017 A1 就是一篇中文期刊论文**，主题与 B题高度相关
   （bearing-only + UBB + set-membership），而 OpenAlex 与 Crossref **都召回不到它**
   （见 §2.1）。此外补检命中的 CCC 2024 群目标 bearing-only 论文
   （`10.23919/ccc63176.2024.10661907`）也是同一方向的弱信号。
   **本轮未检索中文源**——这是本轮最大的覆盖缺口。
8. **D/E/F 簇未系统检索。** D 簇（多目标搜索+定位+路径）本轮通过 A 簇补检
   间接收获 4 篇（Reynaud/Reboul/Ibenthal），但仍不完整；E 簇（定向干扰源 /
   有限视场）与 F 簇（negative information）按指示未系统检索。意外命中：
   Chen et al. 2026（arXiv:2607.12515）关于"横向运动是可观测性必要条件"的分析，
   与问题 4 的定向源排查可能相关。
9. **本轮 10 次查询中 1 次零返回（Semantic Scholar），3 次仅部分有效**
   （查询 1 与查询 3 未能解析出 A1 的标题原文——**原因现已查明：该文是中文期刊论文，
   OpenAlex 与 Crossref 都不索引它**，而不是标题有问题、更不是论文不存在；
   查询 9 被 cs.DS 的 worst-case-analysis 文献淹没）。这些失败已逐条记录在
   `raw/round1_correction_A.json`，其 `query_totals` 与本表的统计口径严格一致
   （fully 6 / partial 3 / ineffective 1）。

---

## 8. Next-step Recommendation

**推荐 A：对 Tier 1 的 6 篇获取全文深读**（本轮按要求未下载任何 PDF）。

**理由：** 修正后的图景改变了下一轮的优先级。Round 1 曾建议"深读 9 篇 anchor +
再做一轮 L2 换词汇重搜"；补检已经用 10 次查询完成了那个"换词汇重搜"，
并且**推翻了它的前提**（A 簇不是空白，而是术语没选对）。因此现在最缺的不是
更多检索，而是**把已找到的直接论文读透**：

- 问题 1 的算法骨架在 **Isler & Bajcsy 2006** 与 **Calafiore 2026** 的正文里；
  摘要不足以重建。
- 问题 2 的闭式几何在 **Zhao–Chen–Lee 2013** 与 **Yang 2013** 的正文里。
- 问题 3 的决策环在 **Reynaud 2018** 与 **Dehghan 2014** 的正文里。

**补检同义词族（若仍需扩检）**：`guaranteed / robust / interval / set-inversion /
worst-case / minimax feasibility`，以及几何描述词
`intersection of angular sectors` / `angle-only triangulation region` / `bearing polygon`。
本轮已验证：**不含 "bearing" 的策略性措辞召回最好。**

**仍不建议 citation snowball。** 本轮 corpus 的强项集中在少数课题组
（Zhao 组、Kieffer 组、Liu/Zhao 组），snowball 会放大既有偏差。

**中文源（CNKI / 万方）的优先级应当上调。** 2017 A1 是中文期刊论文，两个国际索引
都不召回它；B题本身是中文命题，"示向度""测向""交会定位"这类术语的中文文献很可能是
下一个盲区（见 §7 gap 7）。这是本轮唯一一个**已由具体论文证实**的覆盖缺口。

**本轮修正完成，Round 1 文献检索正式冻结。** 不再继续补搜索；下一阶段是
Tier 1 六篇论文的全文获取与深读。本任务不自动下载 PDF，不进入全文深读。
