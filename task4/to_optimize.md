# Task4 优化建议：向总虚拟时间 6000 s 推进

更新日期：2026-09-12。本文依据题目及附件、当前策略源码和落盘实验。文中的主线现已实现为 `double_ring_optical_clear_probe` 并注册到 CLI；当前默认策略没有改动，也没有调用官方接口。

## 1. 结论与目标口径

**6000 s 值得继续争取，但现有证据还不支持“可靠地在 6000 s 完成”。优先方向是减少覆盖点、补强已发现定向源的定位，以及按实际耗时调度检测。继续只调替代半径、2-opt 或交角权重，预计不足以填平差距。**

实现前先用内存原型验证了 **25 点双环方案**：相同 seed 0–29 上，当前默认均值 7850.94 s；双环且不替代覆盖点为 6657.27 s；双环沿用 550 m 替代为 6485.93 s。当时两种双环配置均只有 29/30 全清，seed 12 留下一个已发现频道。这个失败推动了后续近端光学与完整示向条带兜底；最终实现的扩样结果见下文。

本文将“6000 左右”先解释为：**完整运行到 `/exit` 的总虚拟时间，混合案例均值约 6000 s**。同时报告全清率、P95 和“全清且不超过 6000 s”的比例。它不是程序墙钟时间，也不是题目表格中的“总时间 / 已清源数”。如果要求每局或 P95 都不超过 6000 s，则目标明显更难。

### 实现后的结论

最终候选默认关闭覆盖点替代，并增加两级清除保障：35 m 七圆光学覆盖；常规重捕获失败后，以两排光学点覆盖任一正示向的完整 1500 m、±1.01° 扇区。新抽取的混合 1000 例为 **1000/1000 全清，均值 6622.84 s、P95 7716.41 s**；新抽取的全定向 300 例为 **300/300 全清，均值 7486.88 s、P95 8891.01 s**。详细结果见 [实验报告](../experiments/t4_analysis/outputs/toward6000/REPORT.md)。目标已明显接近，但混合均值仍比 6000 s 高 622.84 s。

题目要求确保全清；现有 HANDOFF 另记录了此前接受的本地案例失败率不超过 1% 的风险口径。本文同时保留这两个层次：几何覆盖证明、有限样本零失败、统计风险界不能互相替代，更不能把少清一个源后的较短时间当作达标。

## 2. 当前 Task4 实际做了什么

任务规则来自 [题目正文](../problem/B题/B题.md)、[附件 1](../problem/B题/附件/附件1.md) 和 [附件 2](../problem/B题/附件/附件2.md)：

- 半径 1800 m 圆域内有未知的 10–16 个源，频道互异，取自 1–20。
- 接收半径未知，范围 1000–1500 m；定向源只向未知的闭半平面发射。
- 示向误差有界于 ±1°，同一地点重复检测不会重新抽样误差。
- 移动速度 5 m/s；一次测量 5 s，切频另加 1 s。动作串行，移动中不能测量。
- 光学清除只要求距离不超过 20 m，与无线电发射方向无关；失败 3 s，成功共 5 s。`/clear` 不切换测向机频道。
- API 不提供真实源数。`no_signal` 可能是无源、超距或位于定向背面，不能直接据此退休频道。

当前 CLI 默认是 `geometry_early_optical_clear_probe`，参数为 `731 / 550 / 2 / 35 / 100`：731 m 格距，550 m 清除点替代半径，最多替代 2 点，35 m 提前光学阈值，100 m 路长余量。

实际继承链为：

```text
geometry_early_optical_clear_probe
  -> early_optical_clear_probe
  -> replacement_aware_clear_probe
  -> clear_probe -> integrated_route -> lattice -> deferred -> base
```

其决策机制和改进空间如下。

| 已实现机制 | 价值 | 当前限制 |
|---|---|---|
| 正示向 ±1.01° 扇区交会、1500 m 距离上界、最小包围圆 | 有界误差下保留真位置；19.5 m 内可安全清除 | 默认定位只使用正示向，未利用负测量或光学失败缩小可行集合 |
| 37 点三角格；清除后替代附近格点 | 有系统发现覆盖，并复用清除行程 | 550 m 替代是经验规则，会改变发现和后续定位几何 |
| 检测点与待清除点联合滚动开放路线、多起点 2-opt | 避免先搜完再集中清除及固定回接 | 主要目标仍是路长，未把逐点检测数量、清除成功概率等统一换算为秒 |
| 在近等长路线中优先首点交角较好者 | 部分减少后续定位观测 | 只看首点，未计信号可见性和可行域预期缩小量；无补测的清除点也可能获得几何奖励 |
| 可行域半径 ≤35 m 时提前尝试光学 | 提前把频道标为 located，省去后续扫描 | 中心失败后回到 active；没有完整的局部光学覆盖兜底 |
| 频道 located/cleared 后退出扫描；按当前频道开始扫描 | 控制重复检测和切频 | 其余 active/unseen 频道通常逐点全扫，缺少逐频道的可测性筛选 |
| 末尾调用重捕获 helper | 处理未定位定向源 | 按频道顺序处理，最多 12 次局部观测；用尽预算仍可能留下 active 后退出 |

代码依据：[公共状态](strategies/base.py)、[联合路线与主循环](strategies/integrated_route.py)、[清除点复用](strategies/clear_probe.py)、[替代感知规划](strategies/replacement_aware_clear_probe.py)、[提前光学](strategies/early_optical_clear_probe.py)、[交角评分](strategies/geometry_aware_clear_probe.py)、[局部定位](strategies/active.py)。

注意：仓库另有 `belief`、`active_clear_probe`、`endgame_clear_probe` 等独立策略，**默认策略没有把它们全部合并**。`belief.py` 中存在粒子可见性评分，但默认继承链没有使用它；不能从 README 的整体介绍推断默认已具备完整正负观测 belief。

## 3. 6000 s 到底需要省在哪里

以第 36 轮 [混合 1000 例汇总](../experiments/t4_analysis/outputs/iterations/iteration36_geometry35_replace550/random1000_fresh/summary.json) 及同目录 `cases.csv` 为当前基准：

| 指标 | 当前混合 1000 例 | 当前全定向 1000 例 |
|---|---:|---:|
| 全清案例数 | 999/1000 | 998/1000 |
| 平均总虚拟时间 | 7878.29 s | 8674.85 s |
| P95 | 8836.33 s | 9792.46 s |
| P99 | 9343.67 s | 10302.60 s |
| 全清且总时间 ≤6000 s | 13/1000 | 0/1000 |

全定向来源为 [对应压力测试](../experiments/t4_analysis/outputs/iterations/iteration36_geometry35_replace550/directional1000_fresh/summary.json)。混合集中这 13 个达标案例全部有 16 个源，与已知数量上限允许提前结束搜索有关，不能外推为常规表现。

设移动距离为 $L$，测量次数为 $M$，切频次数为 $S$，失败光学次数为 $F$，成功清除次数为 $C$，则

\[
T=L/5+5M+S+3F+5C.
\]

| 成本 | 当前均值 | 占比 |
|---|---:|---:|
| 移动 27063.89 m | 5412.78 s | 68.70% |
| 无线测量 405.27 次 | 2026.36 s | 25.72% |
| 切频 372.11 次 | 372.11 s | 4.72% |
| 光学与清除 | 67.04 s | 0.85% |

距离均值 6000 s 还差 **1878.29 s，约 23.84%**。如果其他成本不动，路程必须降至约 17.67 km；如果全靠减少测量及其切频，按每次约 6 s 算，要少测约 313 次，几乎从 405 次降到 92 次。应同时减路程、减测量。

一个用于分解目标的预算是：`L=20 km，M=310，S=280，F=1，C=13`，对应 **5898 s**。这是反向设计预算，不是候选已实现的成绩，更不能把各项单独优化的收益直接相加。

也不能只靠更早退出。当前混合成功案例中，真实末次清除到退出平均相隔 309.26 s；即使用离线真值消除这段成本，成功案例的末次清除时刻均值仍为 7568.49 s。在线又不知道真实数量，不能照此停止。

### 最新官方日志给出的具体瓶颈

[official-run.json](outputs/official-run.json) 的完整账目为：

```text
33568.850376 m / 5 + 520 × 5 + 485 + 12 × 3 + 11 × 2
= 9856.770075 s
```

这里是 11 次成功 / 12 次清除尝试，**不是已确认清除 11/12 个真实源**。11 个已发现频道均清除，但 API 日志无法验证真实总数。

频道 6 在 1543.10 s 和 1838.30 s 已得到两次正示向，第三次却到 9815.91 s 才取得，随后清除。该频道测量 37 次、34 次无信号。最后只剩这个已知频道时，又走了约 5676 m、测量 22 次、耗时 1269.24 s。最后一次清除与退出同刻，这次官方慢不能归因于全清后继续扫描。

因此，需要解决的是“已经发现的源怎样及时获得有效定位并清除”，不能只优化第一次发现。

## 4. 第一优先级：25 点双环覆盖，配套解决稀疏观测后的定位

### 4.1 为什么应改变覆盖点集合

当前 731 m 三角格有 37 点，包含原点，任意不同点距离至少 731 m。若完整访问全部点，纯移动至少为

\[
36\times731/5=5263.2\text{ s}.
\]

现有开放路线能达到 26316 m，因此对这个固定点集，继续换更强 TSP 求解器已经没有纯覆盖路程可省。这只是**完整访问该点集**的下界，不是整个任务的全局下界；当前替代和提前停止可以改变实际点集。

对真实源数不超过 15、完整逐点扫描的无替代版本，至少 5 个不存在频道在 37 点上的测量还要 `5×37×5=925 s`。两项已达 6188.2 s，尚未计切频、有效源定位和清除。

731 m 点集中有 18 点在竞技圆盘外，不能直接删掉：边缘向外发射的定向源可能依赖这些测点。单纯放大格距也不是新答案；900 m 的既有生成方式仍产生 37 点，路线反而更长。

### 4.2 一个可直接验证的双环构造

取中心点 $O=(0,0)$，内外环各 12 点，$k=0,\ldots,11$：

\[
\begin{aligned}
r_o&=1800/\cos15^\circ\approx1863.497,\qquad r_i=980,\\
A_k&=r_o(\cos30k^\circ,\sin30k^\circ),\\
B_k&=r_i(\cos(30k+15)^\circ,\sin(30k+15)^\circ).
\end{aligned}
\]

外环正十二边形外接目标圆盘。用以下三类三角形平铺外多边形，下标模 12：`(O,B_k,B_{k+1})`、`(A_k,B_{k-1},B_k)`、`(A_k,A_{k+1},B_k)`。

| 边类型 | 长度 |
|---|---:|
| 中心到内环 | 980.00 m |
| 内环相邻顶点 | 507.29 m |
| 外环相邻顶点 | 964.62 m |
| 内外环相邻顶点 | 951.33 m |

所有边都小于 1000 m。任一源位于某个三角形内，到三个顶点的距离均小于 1000 m；任何过该源的闭半平面至少含一个顶点。因此，**每个未发现频道都在这些点完成扫描时，无论源方向和接收半径如何，至少有一次可见观测**。这沿用现有三角网的论证，但使用更适合圆域边界的点集。

应保留坐标与三角网检查的数值裕度。该构造保证的是发现，不能推出两次独立示向，更不能推出定位半径一定小于 20 m。

本次对该固定点集计算的现有 2-opt 可行路线为约 **18122.25 m / 3624.45 s**，相比完整 731 m 网格少约 1638.75 s 纯移动，并少 12 个扫描站。实际运行还会增加定位、清除绕行；这不是总时间预测。

### 4.3 实现前的同种子诊断：收益很大，定位兜底还不够

试验采用本地生成器默认混合分布，seed 0–29；仅在内存子类中覆盖 `_search_waypoints()`，其余参数保持 35 m 光学阈值和 100 m 路长余量。结果包含失败局，不能单凭均值判胜。

| 配置 | 全清 | 平均总时 | P95 | 平均路程 | 平均测量 | 全清且 ≤6000 s |
|---|---:|---:|---:|---:|---:|---:|
| 当前默认 37 点、550 m 替代 | 30/30 | 7850.94 s | 8640.11 s | 26639.52 m | 414.77 | 0/30 |
| 双环 25 点、禁止替代 | 29/30 | 6657.27 s | 7577.79 s | 23916.33 m | 305.23 | 3/30 |
| 双环 25 点、沿用 550 m 替代 | 29/30 | 6485.93 s | 7752.29 s | 23294.29 m | 297.13 | 9/30 |

禁止替代版本平均少 1193.67 s；沿用替代版本平均少 1365.01 s。两者均在 seed 12 出现“已发现但未清除”，连禁止替代都发生，说明发现证明成立也不能替代后续定位策略。

事后诊断显示，seed 12 的频道 19 只有一条正示向。原始观测点约为 `(-931.75,-1613.84)`，示向 81.08°；现有单示向候选是“向前 300 m、横移 ±320/±520 m”和“向前 500 m”。五个点都无信号，候选耗尽后仍未清除。真源实际上距原测点约 92 m，固定大步长跨过了有利接收一侧。这个距离仅用于运行结束后的诊断，不能反馈给在线策略。

最终实现采用 **双环无替代 + 下文的局部定位/光学兜底**。现有六邻点证书依赖规则三角格，不能原样套在双环上；550 m 邻近替代也不会自动保留上述证明。实测双环 550 m 替代在 seed 0–99 只有 97/100 全清，因此 CLI 默认明确设为不替代。

## 5. 第二优先级：把已经发现的源可靠地清掉

### 5.1 35 m 可行域的七点光学兜底

当前策略只尝试包围圆中心，失败后等待新示向。可以利用光学不受定向可见性限制的规则，加入一个小范围、有终止上界的局部动作。

若已确认该频道存在，且整个可行域包含在以 $c$ 为圆心、半径 35 m 的圆内：先在 $c$ 清除；失败后，依次访问

\[
q_k=c+22(\cos(k\pi/3),\sin(k\pi/3)),\quad k=0,\ldots,5,
\]

在每个点尝试清除，成功即停。

中心覆盖半径 20 m 内。对离中心 $r\in[20,35]$ 的点，最近六边形顶点的角差至多 30°，距离平方不超过

\[
f(r)=r^2+22^2-44r\cos30^\circ.
\]

该函数凸，区间最大值在端点取得；最大距离约 **19.3732 m <20 m**。所以七个光学圆覆盖整个 35 m 圆。从中心开始，最坏移动 `22+5×22=132 m`，至多 6 次失败及 1 次成功，总成本上界为

\[
132/5+6\times3+5=49.4\text{ s}.
\]

该上界不包括到中心的路程，适用于这里的 35 m 全包含条件；不能用“后验大概率落在 35 m 内”代替，也不能直接用于 45 m 或只有单条长示向带的可行域。

这是一个可证明完成的局部回退。当前默认平均仅 0.763 次光学失败，直接动作成本很小；其主要价值是减少失败后的远距离返工，并补可靠性，不能单凭 49.4 s 上界声称全局均值一定下降。

本次另做了相同 seed 0–29 的内存对照：原网格加入这一回退后，仍为 **30/30 全清，均值由 7850.94 s 降至 7734.46 s，节省 116.47 s**；平均路程由 26639.52 m 降至 26106.99 m，测量由 414.77 次降至 412.57 次，共触发 19 次回退。seed 2 反而慢 103.45 s，说明局部补救改变滚动路线后并非逐例改善。这是初筛结果，尚未与双环组合验证，也不能把 116.47 s 直接从双环均值中相减。

工程上，最后成功点可能是六边形顶点。后续清除点探测、真实格点替代和路线起点必须使用 `self.position`；不能仍把原中心当作成功清除位置。

### 5.2 对长条可行域做“小步补测或光学覆盖”的成本比较

双环使观测更稀疏，常见难点会变成单示向或两条接近平行的示向。建议把 active 源作为可进入联合路线的任务，候选同时包括：改善交角的短侧移点、沿既有正信号一侧的接近点、可行域局部光学覆盖点。

针对 seed 12 暴露的大步长问题，可新增统一的**单示向近端光学前缀**：从该频道的正观测点沿示向，在 20、55、90 m 处依次尝试清除。这三个 20 m 光学圆覆盖误差 ±1.01°、距离 0–100 m 的近端扇区；对距离区间 `[0,37.5]`、`[37.5,72.5]`、`[72.5,100]` 分别代入最近圆心，检查距离平方的凸二次式端点即可验证。

若机器人仍在原观测点，三次均失败的成本为 `90/5+3×3=27 s`，成功最迟在第三点，总成本至多 29 s；若需返回原观测点，必须额外计入返回路程。实现采用统一触发条件：常规无线重捕获仍失败且频道至少有一条正示向时才进入光学补救，不读取真值。前缀只排查近端 100 m；随后用纵向间隔不超过 28 m、横向位于示向中心线 ±14 m 的两排光学点覆盖完整 1500 m、±1.01° 正示向扇区。

在示向坐标中，真源满足 `x∈[0,1500]`、`|y|≤1500 sin(1.01°)<26.5`。它到最近横排的距离不超过 14 m，到最近纵向列的距离也不超过 14 m，因此到最近光学点不超过 `sqrt(14²+14²)<20 m`。这个兜底修复了开发中暴露的 seed 1007、1070 和全定向 seed 3010；代价是少数难例的尾部变长。

例如，把可行域分解为若干可被 20 m 圆覆盖的小块，规划访问这些圆心的短路线，失败后排除已扫区域，成功即停。只有整个残余可行域被这些圆覆盖时，才能声称保证清除。细长示向带可能需要很多光学点，应先算成本，再和“移动 + 再测一次”的预计成本比较；不建议把整条 1500 m 示向带无条件逐点扫完。

局部无线补测的评分应同时考虑信号可见性、到点和接回主线的距离、预期缩小后的可行域。若某个源已见很久、连续失锁或主路线即将远离它，就提高补测优先级，避免等到所有覆盖点访问完才跨场回收。

现有第 36 轮四个落盘失败 `3880268419、289203195、62417761、2581748167` 都是已发现但未清除的定向源；本次双环 seed 12 也属于这个类别。这是优先补强 active 处理的直接证据。

## 6. 第三优先级：按频道选择检测，并用“秒”评价路线

### 6.1 正负观测联合约束，而不是无信号直接排除位置

对已发现频道维护状态 $(x,y,\rho,\text{类型},\phi)$：位置、接收半径、类型和发射方向。负测量必须按析取条件处理：**距离超过接收半径，或位于定向背面**。不能把 `no_signal` 当成以测点为圆心的 1000 m 排除圆。

第一步可先实现不依赖先验的安全跳测：若某 active 源整个正示向可行域都距候选点超过 1500 m，该点不可能收到它，跳过这次测量。这里须计算点到整个多边形的最短距离，包含边和内部；仅检查中心或所有顶点在圆外不够。更完整的可见性状态可进一步排除必然无信号的点。有限粒子全部死亡只说明采样模型不支持某状态，不能据此证明频道不存在。

光学失败的信息更强：对已知存在且未清除的频道，`no_target_in_range` 排除当前位置的闭 20 m 圆，与方向、接收半径无关。其补集通常非凸，不能简单交一个半平面；可用多个多边形、圆盘排除列表或候选单元记录。

对 unseen 频道，优先维持发现覆盖义务；只因估计发现概率低就跳测会改变覆盖保证。应分别实现“可证明没有新信息的跳测”和“有统计风险的概率跳测”。若一个点已无任何必要测量，才能同时消除它的移动成本。

一个简单的严格跳测条件是：已有 16 个互异频道被正观测确认存在时，其他 unseen 频道可立即停止扫描，无需等这 16 个都达到 located。已见源的定位和清除任务仍要完成，不能同时无条件删除它们需要的后续测点。

### 6.2 路线目标需要计入测量服务时间和后续动作

当前 `_plan_route()` 的核心比较是路长及首点交角。建议对少量候选动作/短路线估计：

\[
J=\frac{\Delta L}{5}+5\,\mathbb E[M]+\mathbb E[S]
+3\,\mathbb E[F]+5\,\mathbb E[C]+\mathbb E[T_{\rm remaining}].
\]

信息价值通过预计减少的后续动作体现，避免把“交角 0.8”直接与米或秒任意相加。尤其要计入：

- 该站实际需要检测的频道集合。原地加测一个频道约 5–6 s，偏航 500 m 就先付出 100 s。
- 更早定位到 `located` 可免去后续逐站扫描；默认实现已在 located 时退休扫描，因此不能把同一收益再次计作清除收益。
- 提前光学成功概率、失败后的补救成本，以及成功后真实可替代的覆盖点。
- 清除点究竟会不会补测其他频道。当前没有可替代格点时 `_after_clear()` 直接返回，此时首点“交角奖励”并不会产生对应观测。
- 定向源失锁风险、下次获得不同视角的机会、残局处理时间。

先只对短距离候选做一至两步评价，并保留覆盖约束。历史深度 3 IDA*、更强静态路线搜索已经出现失败或总体变慢；增加深度本身不是收益来源。

## 7. 其他可采用的策略与不宜优先的方向

| 方向 | 建议 |
|---|---|
| 自由检测点与动态覆盖选择 | 在双环之后，联合选择“在哪测、测哪些频道”，而非固定点上只优化访问顺序。用离散候选生成方案，再验证连续几何覆盖 |
| 逐频道覆盖证书 | 设该频道已测点集为 $Q_c$。若对每个可能源位置 $x$，有 $x\in\operatorname{conv}\{q\in Q_c:\lVert q-x\rVert\le1000\}$，则任何发射半平面都被至少一个测点命中。可据此研究安全删除冗余测量；只检查有限网格不能当连续证明 |
| 受路线约束的 belief / 信息规划 | 有潜力，但必须融合当前联合路线并按移动成本筛选候选。直接复用旧 `belief` 或每发现一源就立即追踪，已有额外行程过大的反例 |
| 残局专用策略 | 当 active 很少时，联合规划这些源的补测与清除，不按频道编号处理。未发现频道的覆盖任务仍需保留 |
| 更早结束搜索 | 16 个源全部处理后可利用数量上限；低于 16 时需覆盖证据或明确统计风险模型。不得以 6000 s 截断、发现干旱或“已清 10 个”代替完成 |
| 强化学习 / 完整 POMDP | 可作为后续研究，但当前已有更直接、可解释且成本更低的几何改造。未知官方分布、训练成本及约束验证都是额外负担 |

不建议继续作为主线的参数微调，有如下同种子证据：

| 历史变化 | 样本数 | 平均节省 | 解释 |
|---|---:|---:|---|
| 30 m 提前光学，再加入 geometry | 100 | 268.14 s | 已融入当前默认，不能重复算作未来收益 |
| 光学阈值 30→35 m | 100 | 14.10 s | 配对均值差波动大，远小于 1878 s 缺口 |
| 替代 450→550 m | 300 | 190.30 s | 伴随新增失败，不能无条件继续放大 |
| 当前替代排序→geometry_replacement | 300 | 2.67 s | 同一失败未修复，247/300 局完全不变 |

这些数据分别见第 [26](../experiments/t4_analysis/outputs/iterations/iteration26_geometry_early_optical/random100/summary.json)、[27](../experiments/t4_analysis/outputs/iterations/iteration27_geometry_early_optical35/random100/summary.json)、[35](../experiments/t4_analysis/outputs/iterations/iteration35_geometry35_replace450/random300/summary.json)、[36](../experiments/t4_analysis/outputs/iterations/iteration36_geometry35_replace550/random300/summary.json)、[37](../experiments/t4_analysis/outputs/iterations/iteration37_geometry_replacement/random300/summary.json) 轮同种子目录。不同轮新抽取的 `random1000_fresh` 不能当成配对消融。

## 8. 建议实施顺序与验收

1. **先解决可证明的局部完成问题。** 实现 35 m 七点光学兜底，记录 active 首见到清除时间、失败光学后的返工和残局成本；检查是否真的降低总时，而不只看清除尝试数。
2. **新增双环独立策略，先关闭格点替代。** 保留现有默认作 A/B；针对 seed 12 的宽可行域补测，引入短距离 active 任务。此步骤是争取千秒级收益的核心。
3. **加入安全频道跳测与真实服务时间评分。** 先做硬几何上不可能收到信号的跳测，再做少量短路线评价；每次只改变一个机制。
4. **组合后再测试替代和风险参数。** 双环的边界点和定位补测点不能只凭距离删除；通过新的覆盖证书或新的风险验证后再减少点数。
5. **最后扩样验收。** 目标是未用于调参的本地混合均值接近 6000 s，同时报告全定向表现、全清率和尾部；小样本候选不直接提升为默认。

开发回归至少包括 `12、257、918、3917738334、3880268419、289203195、62417761、2581748167、639107002`，并保留相应失败时的定向概率配置。开发集使用相同种子配对比较；选定方案后，再运行新的混合 1000、全定向 1000 和全向压力集。另检查半径接近 1000 m、源靠近圆周且向外发射、示向近共线等边界条件。

每组输出至少包含：案例全清率、源清除率、失败种子、平均总时、成功条件下平均总时、P95/P99、`P(全清且 T≤6000)`、移动/检测/切频分解、程序墙钟时间。对已见未清案例，应单列可行域形状、失锁点和局部补救是否耗尽预算。

若沿用历史 1% 本地风险门槛，需要报告案例失败概率的单侧置信上界。30 例即使零失败也远不足以支持 1% 风险结论；本次双环已有 1/30 失败，更不能据此宣称通过。严禁把已反复调参的案例再次称作独立留出集。

本地分布目前假设源数离散均匀、位置按面积均匀、接收半径均匀、类型及方向随机。这些都不是官方公布的生成分布。官方日志只能复盘可见动作，不能从另一局的总时推断新策略的官方收益。

## 9. 复现与证据边界

当前基线与候选的复现命令均只调用本地模拟器。已经实际运行的命令、种子清单和结果见 [实验报告](../experiments/t4_analysis/outputs/toward6000/REPORT.md)。下面保留原基线命令，便于复核历史对照。

```bash
python3 -m task4.cli batch \
  --strategy geometry_early_optical_clear_probe --seed-start 0 --cases 100 \
  --lattice-spacing 731 --replacement-distance 550 --max-replaced-waypoints 2 \
  --early-clear-radius 35 --route-length-slack 100 \
  --output-dir experiments/t4_analysis/outputs/toward6000/baseline_0_99

python3 -m experiments.t4_analysis.random_benchmark \
  --strategy geometry_early_optical_clear_probe --cases 1000 \
  --selected-seeds experiments/t4_analysis/outputs/iterations/iteration36_geometry35_replace550/random1000_fresh/selected_seeds.json \
  --lattice-spacing 731 --replacement-distance 550 --max-replaced-waypoints 2 \
  --early-clear-radius 35 --route-length-slack 100 \
  --output-dir experiments/t4_analysis/outputs/toward6000/paired_baseline1000
```

双环现已注册为 `double_ring_optical_clear_probe`；默认 `max_replaced_waypoints=0`。已有 README/HANDOFF 中的历史“当前默认”表述按所指轮次理解；既有 CLI 默认仍是第 36 轮 550 m 配置，尚未自动切换到新候选。

### 历史内存原型复现

下面是实现前两项原型试验的等价复现入口，仅用于还原设计过程。正式候选及扩样应使用实验报告中的 CLI 命令。

```bash
python3 -B -u - <<'PY'
import json
import math
import statistics

from experiments.t4_local.engine import LocalSimulator, SimulatorConfig
from task4.client import InProcessClient
from task4.geometry import distance
from task4.strategies.geometry_early_optical_clear_probe import (
    GeometryEarlyOpticalClearProbeStrategy as Base,
)


class Ring(Base):
    def _search_waypoints(self):
        ro = 1800 / math.cos(math.pi / 12)
        inner = [
            (980 * math.cos(math.pi / 12 + k * math.pi / 6),
             980 * math.sin(math.pi / 12 + k * math.pi / 6))
            for k in range(12)
        ]
        outer = [
            (ro * math.cos(k * math.pi / 6),
             ro * math.sin(k * math.pi / 6))
            for k in range(12)
        ]
        return [(0.0, 0.0)] + inner + outer


class OpticalHexFallback(Base):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hex_fallbacks = 0

    def _clear(self, api, position, channel):
        belief = self.beliefs[channel]
        poly = belief.polygon() if len(belief.observations) >= 2 else []
        eligible = bool(poly) and max(
            distance(position, p) for p in poly
        ) <= 35.0 + 1e-7
        if super()._clear(api, position, channel):
            return True
        if not eligible:
            return False
        self.hex_fallbacks += 1
        for k in range(6):
            angle = math.pi * k / 3
            point = (position[0] + 22 * math.cos(angle),
                     position[1] + 22 * math.sin(angle))
            if super()._clear(api, point, channel):
                return True
        raise AssertionError('Certified seven-disk covering failed')

    def _after_clear(self, api, point, remaining):
        return super()._after_clear(api, self.position, remaining)


def quantile(values, q):
    values = sorted(values)
    index = (len(values) - 1) * q
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (index - lo) * (values[hi] - values[lo])


for label, cls, replacements in [
    ('baseline', Base, 2),
    ('ring_no_replace', Ring, 0),
    ('ring_replace550', Ring, 2),
    ('hex22', OpticalHexFallback, 2),
]:
    rows = []
    for seed in range(30):
        sim = LocalSimulator(SimulatorConfig(seed=seed))
        policy = cls(
            lattice_spacing=731.0, replacement_distance_m=550.0,
            max_replaced_waypoints=replacements,
            early_clear_radius_m=35.0, route_length_slack_m=100.0,
        )
        policy.run(InProcessClient(sim, sim.config.robot_id))
        # Only inspect truth after the complete run; never feed it to policy.
        truth = sim.truth_summary()
        stats = truth['stats']
        row = dict(
            seed=seed, time_s=truth['virtual_time_s'],
            all_cleared=truth['all_cleared'],
            move_m=stats['movement_distance_m'],
            measures=stats['measure_count'],
            fallbacks=getattr(policy, 'hex_fallbacks', 0),
        )
        rows.append(row)
        print(label, json.dumps(row), flush=True)
    times = [r['time_s'] for r in rows]
    print(label, json.dumps(dict(
        n=len(rows), all_clear=sum(r['all_cleared'] for r in rows),
        mean_s=statistics.fmean(times), p95_s=quantile(times, 0.95),
        mean_move_m=statistics.fmean(r['move_m'] for r in rows),
        mean_measures=statistics.fmean(r['measures'] for r in rows),
        success_under6000=sum(
            r['all_cleared'] and r['time_s'] <= 6000 for r in rows
        ),
        failures=[r['seed'] for r in rows if not r['all_cleared']],
        fallbacks=sum(r['fallbacks'] for r in rows),
    )), flush=True)
PY
```
