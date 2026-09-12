# Task4 第二轮优化建议：以全清且总时间不超过 6000 s 为目标

审查日期：2026-09-12；代码基点：`2239799`，同时读取当前工作区最新日志。本文是实现评估与后续策略建议，不代表下述新策略已经实现或通过验收。

**建议以双环策略为主要改进起点：优先加入“发现满 16 个后的专用收尾”、清除点的选择性补测和可见性约束下的联合定位。19 点三角单元方案值得保留，但需要先解决边界发现缺口和过大的局部绕行，不能仅凭骨架短就作为更快方案。**

最新在线日志已有 **16 个互异频道清除成功、总虚拟时间 5681.44 s** 的双环案例，因此 6000 s 并非只能停留在设想。不过，本地双环混合 1000 例的全清且达标率只有 **10.60%**；目前证据支持“部分局能够达到”，还不支持“通常或每局都能达到”。

## 1. 当前实现和任务约束

先区分三个版本，避免沿用旧文档中的“当前”表述：

| 版本 | 实际位置与状态 | 主要机制 |
|---|---|---|
| `geometry_early_optical_clear_probe` | [CLI](cli.py) 仍采用的默认值 | 731 m 三角格、清除点替代、滚动开放路线、示向交角排序、35 m 提前光学；550 m 替代是有漏清记录的经验设置 |
| `double_ring_optical_clear_probe` | [最新在线日志](outputs/official-run.json) 使用的策略；也是本文主要建议起点 | 25 点双环发现覆盖，默认不删除覆盖点；继承联合路线，加入七圆光学及完整正示向条带兜底 |
| `sequential_triangle_clear_19` | [新实现](strategies/sequential_triangle_clear_19.py)，仅有轻量实验 | 固定 P1→P19、900 m 间距、24 个三角单元；新单元闭合后立即安排局部检查和清除，固定下一主点为局部路线终点 |

最新日志与 README 中旧的“11 个清除、9856.77 s”并非同一份当前结果。本文读取的 `official-run.json` SHA-256 为 `06fafa1eb1c1f398c8a1ca8a5b139e3a60a3bd31b7b950b148735c381c66d0f9`。在题目“最多 16 个、频道互异”的规则下，16 个互异频道清除成功足以判定该局全清；日志不能提供源类型分布，也不能用于估计总体成功概率。

依据[题目](../problem/B题/B题.md)与[接口附件](../problem/B题/附件/附件2.md)：

- 源数未知，为 10–16；20 个频道，每频道至多一源；源在半径 1800 m 圆内，机器狗可以到圆外检测。
- 接收半径未知，为 1000–1500 m；定向源只在一个未知的闭 180° 半平面发射。一次无信号不能直接证明不存在，也不能直接排除测点周围的圆盘。
- 示向误差有界，原地重复测量不会消除误差。光学清除半径为 20 m，清除与无线发射朝向无关。
- 本文的时间是最终 `/exit` 时的**总虚拟时间**，不是程序实际运行时间，也不是题目要求另报的“总时间/已清源数”。`/exit` 不要求回原点。

设总路程为 $L$，测量数为 $M$，实际切频数为 $S$，光学尝试数为 $O$，成功清除数为 $C$，则

\[
T=L/5+5M+S+3O+2C.
\]

`/clear` 不改变接收机频道，也不产生切频费用。6000 s 应作为 **“全清且 T≤6000”** 的联合目标；在 6000 s 强制退出、遗漏难源后取均值，都不能算达成目标。

## 2. 现有证据：双环更接近目标，19 点还没有兑现收益

| 策略/样本 | 全清案例 | 平均总时(s) | P95(s) | 全清且 T≤6000 |
|---|---:|---:|---:|---:|
| CLI 默认，历史新抽混合 1000 | 999/1000 | 7878.29 | 8836.33 | 13/1000 |
| 双环，新抽混合 1000 | 1000/1000 | 6622.84 | 7716.41 | 106/1000 |
| 双环，新抽全定向 300 | 300/300 | 7486.88 | 8891.01 | 1/300 |
| 19 点，混合 seed 0–9 | 9/10 | 8327.19 | 小样本不作尾部推断 | 0/10 |
| 19 点，全定向 seed 100–104 | 3/5 | 8396.26 | 小样本不作尾部推断 | 0/5 |
| 19 点，全向 seed 200–204 | 5/5 | 7290.28 | 小样本不作尾部推断 | 0/5 |
| 双环，当前单局在线日志 | 16/16 个源 | 5681.44 | 不适用 | 1 局达到 |

来源：[默认历史汇总](../experiments/t4_analysis/outputs/iterations/iteration36_geometry35_replace550/random1000_fresh/summary.json)、[双环混合](../experiments/t4_analysis/outputs/toward6000/final_random1000/summary.json)、[双环全定向](../experiments/t4_analysis/outputs/toward6000/final_directional300/summary.json)、[19 点实验报告](outputs/sequential_triangle_clear_19_light/EXPERIMENT_REPORT.md)。不同新抽样本之间不是配对消融，不能把表中差值全部归因于某个单项改动；19 点均值包含漏清局。

### 2.1 距离 6000 s 的缺口有多大

| 平均成本 | 双环混合 1000 | 19 点混合 10 |
|---|---:|---:|
| 路程 | 23762.91 m | 33946.95 m |
| 移动时间 | 4752.58 s | 6789.39 s |
| 测量 | 303.856 次 / 1519.28 s | 249.5 次 / 1247.50 s |
| 切频 | 279.36 s | 224.40 s |
| 光学及清除 | 71.62 s | 65.90 s |
| 距离 6000 s 的平均缺口 | 622.84 s | 2327.19 s |

双环移动占总时约 71.76%。保持其他成本不变，路程要降到 **20648.72 m**，相当于少走 **3114.19 m（13.1%）**。可以把“少走 2000 m，再净减少约 38 次带切频的测量”作为一组工程预算示例，约节省 628 s；这是设计配额，尚不是实验收益，不能把两项可能重叠的收益重复相加。

19 点的情况更严重：移动本身已超过 6000 s。固定骨架仅 16200 m，但局部/收尾额外路程平均 **17746.95 m**。保持非移动成本 1537.80 s 不变，6000 s 只允许总路程 **22311 m**，即局部/收尾部分降至 **6111 m**，需要削掉约 **65.6%**。若再修补边界覆盖，还要重新分配这笔预算。

这里“额外路程”沿用报告中“实际路程减计划骨架”的统计口径。代码在某主点没有任何检测动作时仍递增主点计数及骨架距离，因此后续研究 16 源跳点收益时，应从实际 actions 的相邻坐标重新分段，不能直接把诊断字段当成实际经过的路段。

19 点与同 seed 的 `early_optical_clear_probe` 比较，少测量节省 1060.00 s、少切频节省 202.80 s，但移动增加 1299.74 s，最终反而慢 35.54 s。**其主要问题是局部决策造成的折返，不是检测点数量还不够少，也不是局部 TSP 求解不够精确。**

## 3. 必须区分 16 源与少源，但线上只能按已观测信息切换

以下从双环混合 1000 例的 [cases.csv](../experiments/t4_analysis/outputs/toward6000/final_random1000/cases.csv) 按运行结束后的真实源数重算，所有行均全清：

| 真实源数 | 样本数 | 平均总时(s) | P95(s) | 全清且 T≤6000 |
|---|---:|---:|---:|---:|
| 10 | 148 | 6629.24 | 7514.62 | 10/148（6.76%） |
| 11 | 119 | 6595.69 | 7429.56 | 7/119（5.88%） |
| 12 | 157 | 6633.39 | 7780.04 | 12/157（7.64%） |
| 13 | 150 | 6678.87 | 7577.96 | 11/150（7.33%） |
| 14 | 139 | 6709.61 | 7724.55 | 4/139（2.88%） |
| 15 | 145 | 6652.52 | 7663.31 | 17/145（11.72%） |
| 16 | 142 | 6452.81 | 7940.38 | 45/142（31.69%） |
| 合并 10–15 | 858 | 6650.98 | 7618.82 | 61/858（7.11%） |

16 源组更容易出现提前完成的快局，但其 P95 仍高，不能解释为“16 源普遍容易”。在[全定向 300 例](../experiments/t4_analysis/outputs/toward6000/final_directional300/cases.csv)中，16 源组 47 例均值 **7814.46 s**、P95 **9372.87 s**，仅 1 例达标；少源组 253 例均值 **7426.03 s**，无达标。数量上限带来的停止优势，可能被更多定向源的定位成本抵消。

这里有两个不同的在线阶段：

1. **已发现频道数 K=16：** 其余 4 个频道必然不存在。立即停止这些频道的检测，取消纯粹用于发现新源的覆盖义务，转为对剩余已见源的联合定位/清除；必要的测点继续作为定位候选。只有全部清除才退出。
2. **K<16：** 不能知道真实数量恰好等于 K。继续完成未见频道的发现覆盖，或取得逐频道“不可能存在”的几何证据。已清 10 个、长时间无新发现，都不是完成证明。

当前双环继承的 [IntegratedRouteStrategy.run](strategies/integrated_route.py) 直到 **16 个 located/cleared** 才清空剩余覆盖点，比“16 个已发现”更晚；在此之前仍扫描未见频道。19 点的 `_main_scan_channels()` 已有 K=16 时跳过 unseen 的逻辑，不能把它再次算作该策略的新优化，但其主点与闭合格流程尚未转为自由收尾。

源少不必然省时：在双环完整覆盖情况下，N=10 有 10 个不存在频道，仅这些频道就需 `25×10=250` 次检测，即 1250 s，再加切频；N=15 对应 125 次、625 s。19 点对应 190/95 次，但其边界发现覆盖不完整，不能把这部分减少全部当成无风险收益。

事后真值还显示：双环混合 1000 例的真实末次清除时刻均值为 **6434.70 s**，最终退出为 **6622.84 s**；其中少源组清完后的继续排查平均 **219.28 s**。按真实末次清除≤6000 计有 291/1000，按可执行的最终退出口径只有 106/1000。即使拥有真值消除尾扫，平均仍超过 6000 s；因此提前停止不能解决全部缺口。

## 4. 双环主线：优先实施的三个改动

### 4.1 K=16 后切换到联合、开放的定位清除任务

将“发现义务”和“定位价值”拆开。K=16 后，不再把未访问双环点全部列为必访点；仅保留对 active 频道有实际价值的点，同时加入短侧移、光学清除与局部光学覆盖任务。以当前真实位置为起点，终点自由。

不能简单把 `remaining.clear()` 的条件改成 K=16 后就认定优化完成：当前 `_resolve_active_channels()` 按频道顺序调用逐源重捕获，可能把少走的覆盖路线转化为更大的残局折返。应先保留其光学完成兜底，再把几个剩余源一起安排，比较“继续在未来覆盖点自然定位”和“现在专门定位”的代价。

该改动最直接针对 16 源组。需要记录 K 首次达到 16 的时刻、当时 active 数、此后的未见频道测量数、覆盖移动、定位移动与收尾时长；这些日志才能确定实际可节省多少，而不是以“剩余多少点×点间距”估算全部收益。

### 4.2 将清除点补测与删除覆盖点解耦

**双环名字中虽然有 `clear_probe`，默认情况下成功清除后实际上不补测其他频道。** 原因是默认 `max_replaced_waypoints=0`，而 [ClearProbeStrategy._after_clear](strategies/clear_probe.py) 在没有可替代点时立即返回。双环的覆盖保证因此得到保留，但已经付出移动成本的清除位置未用于协同定位。

建议先借鉴 [active_clear_probe](strategies/active_clear_probe.py)，在清除成功的真实位置，选择少量值得检测的 active 频道，无需删除任何覆盖点。优先考虑：

- 当前位置有较强可见性证据，而且一次测量有望把可行域压进光学可覆盖范围。
- 该源已有较长时间未收敛，后续主路线将远离它。
- 本次补测预期可免去一次专门绕行，或者让该频道提前达到 located、退出后续扫描。

每个补测仍需 5–6 s，不能把每次清除变成重新扫 20 个频道。判断门槛应是“预期节省的后续时间大于本次成本”；先试最多 1–2 个高收益 active 频道。首点示向几何奖励也只应计入**实际会被检测**的频道，修正当前 `_active_geometry_value()` 与动作执行不一致的情况。

### 4.3 用可见性和可行域收缩选择补测，缩短光学兜底路线

当前几何排序主要奖励交角，未充分约束定向可见性；“交角好但没有信号”不会帮助定位。建议维护与全部观测相容的 `(位置 x, 接收半径 ρ, 类型, 发射方向 φ)` 状态，先筛掉不可能接收的候选，再比较测后可行域和总成本。有限粒子可用于收益排序，但不能用粒子耗尽证明频道不存在。

有一个可直接利用的保守性质：**同一未清除频道的多个正观测站的凸包内，均保持无线可见。** 对真实源而言，可见域是一个圆盘，或圆盘与闭半平面的交，二者都凸；因此正观测站间的线段也可见。可从这些线段生成低失锁候选，再检查其距离和新示向几何价值。只有一个正观测站时，这个凸包没有可移动空间；沿“估计中心到旧观测站”的方向接近仍是启发式，不能说必然可见。

双环的光学收尾已有保障，但[完整条带兜底](strategies/double_ring_optical_clear_probe.py)固定使用第一条正示向，按 1500 m 长、两排共 110 个候选点搜索，未利用其他示向形成的较小交集。建议对全历史可行域做局部光学圆覆盖，并选择离当前点近、覆盖残余区域大的访问顺序；保留完整条带作最后回退。已知源光学失败会排除一个 20 m 圆盘，应减少之后的重复覆盖。

“光学失败后重回无线定位”和“继续少量光学点”的成本要显式比较。已有 35 m 七圆覆盖可在中心失败后，用半径 22 m 六边形完成补救，从中心起最坏总成本 49.4 s（含中心尝试，不含到中心的路程）；为补一条示向绕行几百米常常更贵。但该保证要求**整个可行域**在 35 m 圆内，不能只凭估计误差或局部单元内的交集。

## 5. 19 点候选：先修完整性，再压缩局部绕行

### 5.1 19 点并未认证覆盖整个圆域

[triangle_cells.py](strategies/triangle_cells.py) 的 24 个三角形拼成一个内接正六边形。边长 900 m 的单元内部，源到三个顶点都不超过 900 m，任何经过源的发射半平面至少包含一个顶点，因此顶点检测可保证发现该单元内的源。

但是，六边形与目标圆之间有六个圆弓区域，其总面积占比为

\[
1-\frac{3\sqrt3}{2\pi}\approx17.30\%.
\]

这是**缺少该三角覆盖证书的面积占比，不是漏检概率**。位于这些区域、朝外发射的定向源可能始终不被发现。已有 mixed seed 2、全定向 seed 102 是这一类；全定向 seed 103 则是已发现却未清除。必须分别处理“没发现”和“没清完”，增加 residual 检查次数只能尝试修后者。

少源分支尤其不能以“19 点扫完”为全清依据。可选的修复路线是使用已认证双环覆盖，或重新设计外接边界及其连续三角覆盖证书；仅追加几个边界点、仿真网格上没漏，都不足以自动获得保证。

一个可以保留原三角单元结构的具体替代设计是：将 P9/11/13/15/17/19 六个角点外移至半径 `1800/cos(15°)+0.25≈1863.7471 m`，再在 30°、90°、150°、210°、270°、330° 添加同半径六站，其他 13 点保留。原24格调整后，每个圆弓方向增加两格，共36格；最大三角边约 **964.7465 m<1000 m**，外边界为包含目标圆的正十二边形，恢复全域发现证书。

按原次序在 P8/10/12/14/16/18 后插入对应外站，完整主路线约 **18585.42 m**，比原骨架增加 **477.08 s** 的移动，还须承担新站检测。现有双环点集经仓库 `open_path_two_opt()` 产生的纯覆盖路线约 **18123.92 m**，更短约92.30 s。因此这个25点变体主要用于保留单元组织，并非已知更快的完整策略；上述数字仅是几何路线计算，没有包含定位清除。

### 5.2 单元闭合应产生任务，不应强制立即做完

当前 `_settle_cells()` 只把新闭合单元的任务送入固定起点/终点的 Held–Karp DP，每做一个动作重建任务，然后才去下一主点。DP 对当时那一组静态任务的路线是精确的，但无法选择“等待下一主点自然补到示向”、跨单元共享一次移动，或改变收尾时机。

建议保留单元作为覆盖、排除和定位假设的管理方式，把局部任务放入跨相邻 2–3 个单元的池，允许延期；每轮同时比较：现在清除、短程补测、顺路再观测、推迟至下一个主点。失败/困难任务带着全部历史留在池中，不按单元重新开始定位，也不永久绑定一个源只属于某个单元。

局部任务点同样可选择性检测多个 active 频道，清除点也可复用。已经收到 `near` 时，只需原地 5 s 即可清除，应直接处理；当前主扫描把它标记 located，可能等相关单元闭合后再折回，且测试 `test_near_vertex_is_cleared_when_its_cell_closes` 固化了这个行为。

### 5.3 让已排除区域真正缩小定位域，复用双环光学兜底

目前 `_excluded_cells` 记录三顶点全部无信号的单元，但 `_global_region()` 仍只返回全历史正示向多边形；失败光学也主要用于“中心移动至少 5 m 才重试”的冷却。可以维护

\[
P_c^{\rm remaining}=P_c^{\rm bearings}
\setminus\bigcup\{\text{已认证排除的单元}\}
\setminus\bigcup\{\text{该已知源的失败光学圆盘}\}.
\]

这个集合通常非凸，需要多片多边形/圆盘排除列表，不能简单再取一个凸交集；计算清除半径时要包住全部残余片，也要保留边界圆弓。对“假设源在某个 900 m 单元内”的状态，顶点无信号可归因于定向背面，而非距离不足，从而联合约束发射方向；该条件不能推广到任意测点。

当前局部检查上限 3/2 次、residual 上限 4 次只是预算，不是定位或清除保证。可把双环的七圆与完整正示向光学回退引入已见源收尾，先修 seed 103 这类已见未清，再研究更省时间的可见性补测。

本次另用内存子类做了一个针对该风险的本地检查：固定真实源数16、seed 0–29、定向生成概率0.5。原19点策略 **19/30全清、均值8588.95 s、0/30全清且≤6000**；在下一个主点开始前，一旦已经发现16频道便直接转现有 residual 的变体为 **10/30全清、均值7669.73 s、1/30全清且≤6000**。这只是失败机制诊断，不能把少约919 s说成优化收益。缺少后续示向而又沿用4次残余检查上限，会增加未清源；第4.1节的阶段切换必须配套有完成保障的收尾。复现代码见文末。

### 5.4 收尾去掉虚构返航终点，但不要预估为千秒级收益

`_settle_residual()` 把 P19 作为固定终点纳入 DP，而任务完成后实际直接 `/exit`。应使用终点自由的开放路线。注意目前没有真的执行一次回 P19 的移动，所以不能把“最终位置到 P19 的距离/5”当成直接节省；收益只能来自任务顺序变化，需配对实测。

## 6. 其他可采用的策略

| 策略方向 | 如何用于本题 | 适用阶段与限制 |
|---|---|---|
| 按秒计算的短视野信息规划 | 对候选位置及频道集合估计 `移动/5 + 5×测量 + 切频 + 光学 + 后续剩余时间`，信息价值体现为未来成本下降 | 双环、19 点都适用；先做一至两步，避免未经校准的交角权重主导长距离移动 |
| 逐频道覆盖证书与选择性扫描 | 对每个未见频道维护实际已测点集；只有证明它没有剩余可见性假设时才退休 | 少源场景的长期重点；删一次测量不一定能删该站移动，收益要分别核算 |
| 发现覆盖与局部定位混合 | 用经过认证的少量全局点负责发现，用三角单元管理历史，再以联合任务池定位清除 | 推荐的组合方向；应继承19点的信息组织方式，重新评估其强制访问/结算顺序 |
| 面向光学清除的区域访问 | 规划覆盖残余可行域的 20 m 光学圆，按成本比较中心、圆覆盖、再测示向三种动作 | 已见难源；不需要继续精确估计发射方向，不应无条件扫完整条带 |
| 显式风险的概率提前停止 | 估计尚有源的后验概率，在预先声明的风险门槛下停止 | 仅作为另行评价的风险方案；本地源数、位置、方向分布并非官方已知分布，不能替代保证全清 |

逐频道发现证书的一个充分条件是：对每个可能源位置 $x$，其 1000 m 内的已测点满足

\[
x\in\operatorname{conv}\{q\in Q_c:\|q-x\|\le1000\}.
\]

此时任何经过源的闭半平面均包含至少一个射程内测点。如果这些测量全部无信号，该频道不可能存在。这解释了三角覆盖为什么有效，也为安全删除冗余检测提供方向；有限采样检查并非连续区域证明。

上述有界示向集合和传感点选择，可参考 [Sensor placement and selection for bearing sensors with bounded uncertainty](https://ieeexplore.ieee.org/abstract/document/6630920)；分批自适应路径规划可参考 [Informative Path Planning with Limited Adaptivity](https://proceedings.mlr.press/v238/tan24a.html)。这里借鉴其建模思路，未将文献的近似保证直接套到本题：未知源数、定向失锁、清除动作与原研究假设不同。

不建议优先继续放大替代距离、只换更强 TSP 求解器、增加深度、原地重复示向平均，或直接训练完整强化学习策略。现有数据已经指出更具体的移动和信息复用缺口；程序墙钟时间也应单独监测，减少 Python 计算并不会自动减少题目虚拟时间。

## 7. 实施与验收顺序

1. **先统一基线和诊断。** 显式指定策略及参数，以双环无替代作主要对照；补记 K=16 时刻、每阶段路程、每频道首次发现到清除时间、清完后的确认成本，以及光学兜底触发次数/路程。
2. **双环先做单项配对消融。** 分别测试 K=16 的任务切换、清除点选择性补测、残余光学域缩减，再组合。前两项不需要删除发现覆盖点，不应预先混入更激进的覆盖替代。
3. **19 点先修失败，再谈快。** 必测 mixed seed 2、全定向 102/103，分开验证圆弓发现与已见收尾；之后比较跨单元任务池、局部多频道复用、开放收尾。原报告的 10/5/5 样本无法支持尾部或低失败率结论。
4. **源数与定向比例交叉分层。** 开发时固定 N=10、13、15、16，并覆盖定向比例 0、0.5、1；最终对 N=10…16 全部报告。固定数量只属于离线生成参数，在线策略不能读取真实 N。另构造最小接收半径、近圆周向外、单示向近源、近共线、多个难源相距很远等边界局。
5. **候选锁定后做未用于调参的验证。** 报全清率、源级清除率、均值、成功局均值、P95/P99、最大值、`P(全清且 T≤6000)`及置信区间；16/少源和定向比例分别展示。保留失败的完整日志、种子、配置。调过的 seed 不能再称独立留出集。

“混合均值≤6000”“至少95%的案例全清且≤6000”“所有符合题目的案例都≤6000”是不同目标。建议近期先提高分层联合达标率，再争取 P95≤6000；目前不能给出最坏情况 6000 s 保证。历史文档里的1%风险门槛也不等于允许以漏源换取本次目标。

## 8. 复算与后续实验入口

本次主表来自现有落盘数据的只读重算，另做了第5.3节的本地固定16源诊断和第5.1节的几何计算，没有重新进行正式测试。以下命令在仓库根目录执行，输出至终端；分位数与现有 benchmark 一样采用线性插值：

```bash
python3 -B - <<'PY'
import csv
import json
import statistics as st
from pathlib import Path

root = Path('experiments/t4_analysis/outputs/toward6000')
for name in ('final_random1000', 'final_directional300'):
    with (root / name / 'cases.csv').open() as f:
        rows = list(csv.DictReader(f))
    print(name)
    groups = [(str(n), [r for r in rows if int(r['emitter_count']) == n])
              for n in range(10, 17)]
    groups += [('10-15', [r for r in rows if int(r['emitter_count']) < 16]),
               ('all', rows)]
    for label, group in groups:
        times = sorted(float(r['virtual_time_s']) for r in group)
        i = (len(times) - 1) * .95
        lo, hi = int(i), min(int(i) + 1, len(times) - 1)
        p95 = times[lo] + (times[hi] - times[lo]) * (i - lo)
        ok = lambda r: r['all_cleared'].lower() == 'true'
        hits = sum(ok(r) and float(r['virtual_time_s']) <= 6000 for r in group)
        tail = st.fmean(float(r['virtual_time_s']) - float(r['last_clear_time_s'])
                        for r in group if ok(r))
        print(label, len(group), round(st.fmean(times), 2), round(p95, 2),
              hits, f'{hits/len(group):.2%}', 'post_clear_s', round(tail, 2))
    mean = lambda key: st.fmean(float(r[key]) for r in rows)
    nonmove = mean('virtual_time_s') - mean('movement_time_s')
    print('movement_s', mean('movement_time_s'), 'measure_s', 5*mean('measure_count'),
          'switch_s', mean('channel_switch_count'),
          'optical_clear_s', 3*mean('optical_count') + 2*mean('cleared_count'),
          'distance_budget_6000_m', 5*(6000-nonmove))

log = json.loads(Path('task4/outputs/official-run.json').read_text())
result = log['strategy_result']
print('current_log', result['strategy'], len(set(result['cleared_channels'])),
      result['final_virtual_time_s'])
PY
```

后续固定源数实验应使用现有 [run_batch](../experiments/t4_local/benchmark.py)，向 `simulator_config` 传入 `min_emitters=N, max_emitters=N`；CLI 当前没有固定源数参数。相同 N、定向配置、seed 清单下进行策略配对。建议输出到新的 `experiments/t4_analysis/outputs/toward6000_v2/`，并保存策略参数和 seed 清单；不要覆盖本文所引用的基线。

例如以下是**后续实验入口，本文未运行该批次**；真值只由 benchmark 在策略运行结束后用于评分：

```python
from pathlib import Path
from experiments.t4_local.benchmark import run_batch

run_batch(
    'double_ring_optical_clear_probe',
    list(range(12000, 12030)),
    Path('experiments/t4_analysis/outputs/toward6000_v2/base_n16_mixed'),
    {'max_replaced_waypoints': 0, 'early_clear_radius_m': 35,
     'route_length_slack_m': 100},
    {'min_emitters': 16, 'max_emitters': 16, 'directional_probability': 0.5},
)
```

### 本次固定16源诊断的自包含复现

下面代码复现第5.3节的两组结果，不修改策略源码，不发 HTTP 请求。原始探索脚本与逐例结果保存在 `/tmp/task4_openend_probe.py`、`/tmp/task4_openend_probe.json`；以下入口仅保留本文讨论的两个变体，将复算结果另存 `/tmp/task4_to_optimize2_repro.json`。固定16源仅传给本地环境，策略切换仅使用已观测的频道状态。

```bash
python3 -B - <<'PY'
import json
import statistics
import time
from pathlib import Path
from experiments.t4_local.engine import LocalSimulator, SimulatorConfig
from task4.client import InProcessClient
from task4.strategies.sequential_triangle_clear_19 import SequentialTriangleClear19Strategy

class Found16(Exception):
    pass

class FinishAfter16(SequentialTriangleClear19Strategy):
    def _main_scan_channels(self, point_id):
        if sum(b.status != 'unseen' for b in self.beliefs.values()) == 16:
            raise Found16()
        return super()._main_scan_channels(point_id)

    def run(self, api):
        started = time.perf_counter()
        try:
            return super().run(api)
        except Found16:
            self._settle_residual(api, self.position)
            result = self._finish(api, started)
            result.diagnostics = self._diagnostics()
            return result

rows = []
for seed in range(30):
    for cls in (SequentialTriangleClear19Strategy, FinishAfter16):
        sim = LocalSimulator(SimulatorConfig(
            seed=seed, min_emitters=16, max_emitters=16,
            directional_probability=0.5))
        policy = cls()
        result = policy.run(InProcessClient(sim, sim.config.robot_id))
        truth = sim.truth_summary()  # 仅在运行结束后评分
        rows.append(dict(seed=seed, variant=cls.__name__,
                         time=result.final_virtual_time_s,
                         cleared=truth['cleared_count']))
Path('/tmp/task4_to_optimize2_repro.json').write_text(json.dumps(rows, indent=2))
for name in sorted({r['variant'] for r in rows}):
    group = [r for r in rows if r['variant'] == name]
    print(name, 'all_clear', sum(r['cleared'] == 16 for r in group),
          'mean_s', statistics.fmean(r['time'] for r in group),
          'all_clear_6000', sum(r['cleared'] == 16 and r['time'] <= 6000 for r in group))
PY
```
