# Tier 1 Wave 2 + Song 综合：CUMCM B题建模收敛与证据边界

## 范围与状态

本综合继承 Wave 1 的 Isler & Bajcsy (2006)、Zhao, Chen & Lee (2013)、Reynaud et al. (2018)，并加入 Calafiore (2026)、Dehghan et al. (2014) 和 **post-Round-1 teammate-supplied supplemental anchor** Song, Kim & Yi (2012)。`[Paper]` 是全文可定位结论，`[B-inference]` 是本项目推论。

Yang et al. (2013) 的正式书目信息已核实，但期刊全文在本轮合法渠道不可得，故其 deep-reading 状态为 **BLOCKED**；本综合只把摘要支持的 Gaussian-prior / heterogeneous-sensor 方向作为 provisional evidence，不引用未核实的公式、定理和实验。

## A. P1 还需要多少文献？

- [Paper] Calafiore 将 UBB range 的 exact nonconvex shell intersection、d.o.m. polyhedron、convex localization outer set、outer box/ellipsoid 清晰分层；outer box 有 containment guarantee，outer ellipsoid是 S-procedure 下的次优外包络（Secs. 2-5）。
- [B-inference] B 题 bearing sector 本身可写成两个半平面；P1 的真正工作仍是半平面交、圆盘裁剪、凸多边形直径、最小包围圆和数值稳健性。Calafiore 的 range-only 代数不解决这些算法。
- **结论：P1 literature work can stop.** Calafiore 保留为 formalism/citation support，不值得继续扩展；实现与证明应转向可复现计算几何。

## B. P2 的最终候选主线

### 1. Hard-bound robust strategy（推荐主模型）

- [B-inference] 题目事实：同一地点误差固定，跨地点误差仅知 $\varepsilon\in[-1^\circ,1^\circ]$。第一测量形成 exact wedge $U_1$。
- 对候选第二点 $s_2$，在所有 $x\in U_1$ 和 admissible second errors 上计算更新集 $U_2$ 的 worst-case diameter/area；加上可达域、1000 m guaranteed-reception 逻辑和移动/测量时间。
- 这是唯一直接兑现 hard containment 的主线；Isler 支持 measurement-set intersection，Zhao 的近正交几何负责生成候选，Calafiore 支持 exact/outer approximation 的术语纪律。

### 2. Probabilistic expected-performance strategy（备选模型）

- [B-inference] 在 hard support 内另设 uniform、triangular、truncated centre-concentrated 或 simulator empirical density，计算 expected diameter/entropy/posterior covariance。
- 这是额外 modelling assumption，不得写成题设。Yang 摘要支持“Gaussian prior + updated information”方向，但正文 BLOCKED，不能作为精确公式的唯一依据。

### 3. FIM/CRLB strategy（benchmark）

- [Paper] Zhao 的 bearing FIM 与固定权重下二维两 sensor 正交最优已在 Wave 1 核实；[B-inference] 它是局部点估计 benchmark/candidate-generator，不提供 hard ±1° guarantee。
- [B-inference] bounded/truncated density 的 support 随参数平移时，经典 regularity 可能失效；不能直接把 ±1° 换算为 Gaussian $\sigma$。若使用 FIM，需明确平滑 likelihood、Bayesian prior 或重新推导边界项。

### 4. Hybrid strategy

- [B-inference] 先用 Zhao/Yang-style information 或 posterior mass 快速排序候选，再用 hard feasible-set worst-case diameter 做安全复核。推荐结构：`probability proposes -> hard set certifies`。

### Zhao vs Yang 结论

| 问题 | Zhao 2013 | Yang 2013 | B题决策 |
|---|---|---|---|
| target knowledge | coarse point estimate | [abstract] arbitrary Gaussian prior | 第一测量后应保留区域/分布，不只取中心 |
| prior uncertainty | 无 prior covariance | [abstract] 有 Gaussian prior | 概率备选可利用 covariance/belief |
| bearing model | 已全文核实 | [abstract] 包含 bearing-only | 公式主证据暂用 Zhao |
| sequential placement | 非 hard-set online second-point | [abstract] several time steps；online 条件 BLOCKED | 不声称 Yang 直接给出在线第二点算法 |
| objective | D-opt / isotropy | updated information；标量 BLOCKED | 只作 provisional candidate score |
| travel cost | 无 | 期刊版 BLOCKED | B题自行加入 |
| hard guarantee | 无 | 未见已核实保证 | 必须由 robust layer 提供 |

## C. P3：Song / Reynaud / Dehghan 如何分工？

- **Song** = global multi-source probabilistic search/localization：SPOG 同时维护 cell occupancy 与 active-source probability，ridge walking 穿越高概率 components；匿名、间歇 radio source 是其核心。
- **Reynaud** = bounded-set management：已发现目标集合 + 未发现目标可能区域，positive observation 取 inverse image 交，deterministic no-detection 做集合差，一步体积上界驱动动作。
- **Dehghan** = local RF next-waypoint implementation architecture：候选 steering/waypoint、局部 FIM score、move/measure/EKF/update/replan；其 DRSSI/EKF 数学不可迁移。

### Q3 候选 architecture

1. **global search**：用有保证的覆盖路线保证 20 个频道在必要区域被监听；Song 的 occupancy/ridge 思想只用于优先级，不替代 coverage guarantee。
2. **source/channel belief**：每频道 $E_c\in\{0,1\}$，维护 hard region $F_c$ 和可选 belief $p(x_c,y_c\mid H,E_c=1)$。频道天然解决 Song 的 anonymous data association。
3. **detect**：positive bearing 更新 $F_c\leftarrow F_c\cap W$，并用 bounded-support likelihood 更新 belief；no-signal 只做有物理保证的排除/降权。
4. **localize / choose next waypoint**：候选点由 Zhao 近正交几何、belief 高概率区和可达网格产生；采用 Dehghan 的一步滚动结构，以 worst-case diameter / expected information / action time 联合评分。
5. **optical confirm / clear**：当可靠候选已能引导至 20 m 内，花 3 s 光学确认、2 s 清除；5 m 强信号例外按题设直接进入光学。
6. **update undiscovered-source state**：清除后冻结频道，更新全局路线与剩余频道 coverage；这一步对应 Reynaud 的 undiscovered region，但须用 B 题接收模型重建。
7. **repeat / terminate**：终止需由全频道搜索覆盖证书 + 已检测源全部清除共同决定，不能使用 Song 的 (k_{max}) 无新源 heuristic 或 Reynaud 的 known-FoV 空集原样替代。

### Q3 主模型选择

- **推荐：混合。** set-membership 给 bearing hard guarantee 和终止证据；probabilistic belief 给频道/位置/动作排序；Dehghan-style receding horizon 把二者接到可执行动作。
- 纯 set-membership 保守但容易产生大面积未搜索区；纯 probabilistic belief 更高效却不能自动满足“确保全部清除”。

## Reynaud vs Song：核心比较

| 维度 | Reynaud 2018 | Song 2012 | 对 B题含义 |
|---|---|---|---|
| uncertainty style | set-membership | probabilistic SPOG | 推荐 hard set + belief 双层 |
| target count | unknown | unknown；occupied cells 隐式给数量 | B题另知 10-16，可作 termination/check prior |
| target identity | detected target indexed | anonymous transmission | channel = source identity label，大幅简化 association |
| sensor platform | UAV fleet | single mobile robot | Song 平台更接近单狗；Reynaud 多机项删除 |
| positive observation | inverse image 与预测集求交 | RSS likelihood 的 Bayes recursion Eqs. (19)-(20) | bearing 同时做 wedge intersection 与 bounded-support likelihood |
| no detection | known deterministic FoV 的 set subtraction | 无显式 no-signal spatial update；只在 signal arrival 时更新 | B题不得把无信号等同 absence |
| sensing coverage | 已知、FoV 内必检 | robot directional antenna + calibrated RSS；source omni/transient | B题未知 radius + Q4 unknown source direction，均需新 observation model |
| planning | one-step set-volume upper bound | level components 的 ridge + modified TSP，周期重规划 | global ridge/coverage + local one-step score |
| objective | known-target sets + undiscovered area | accelerate occupancy convergence / localization time | 加入全部题设时间项 |
| guarantee | bounded containment，依赖无漏检 FoV | probabilistic threshold；Poisson 条件下 expected search-time bound | hard guarantee 由集合/coverage层承担 |
| directional source | no | no；方向性在 receiver antenna | 两者都需 Q4 adaptation |

## D. P4：no-signal 与仍缺的文献

### 两种“间歇”严格区分

- [Paper] Song transient = **time-domain intermittency**：静止全向源短时、随机发包。
- [B-inference] B 题 directional source = **space-domain visibility**：源在指向 $\phi$ 两侧 ±90° 内辐射；物理机制不同。
- 共同观测结构仅为 `no signal != source absent`。迁移的是 belief-update / negative-evidence logic，不是 Song 的 Poisson 或 RSS likelihood。

### no-signal 的四种解释

对频道 $c$，一次 no-signal 可能是：$E_c=0$；有源但距离超过未知 $R_c\in[1000,1500]$；定向源但机器人位于覆盖角外；或题设允许的接收边界因素。因此：

- [Paper] Reynaud 的 subtraction 依赖已知 deterministic FoV 内必检测；[B-inference] B 题条件不满足，不能直接删位置圆盘。
- [Paper] Song 没有对 no-signal 做显式 spatial Bayes update；[B-inference] 其概率框架仍比 hard deletion 更适合承载弱负证据，但 likelihood 必须由 B 题自行定义/校准。

### 增广状态与计算

令
\[
s_c=(x_c,y_c,\phi_c,R_c,\tau_c),\qquad \tau_c\in\{omni,directional\}.
\]

- [B-inference] dense grid 的 cell 数等于各维离散数乘积；若沿用 Song 的 $O(n^2)$ update，位置×朝向×半径×类型会不可接受。
- **建议顺序：** factorized existence/type + 位置 particles/samples + 条件方向/半径 particles；必要时用 coarse joint particles。只在低分辨率离线 benchmark 中尝试完整 5-D grid。
- hard layer 只删除在所有允许参数下都与观测矛盾的联合状态；belief layer对更可能的 radius/direction 降权。投影到位置时不能把某一朝向被否定误写成整个位置被排除。

### Remaining literature gap

directional source / unknown pointing direction 仍是明确 gap。下一轮只需最小化检索：

- `directional transmitter localization unknown boresight mobile receiver`；
- `passive emitter localization sector coverage negative detection`；
- `joint source position orientation estimation radio directional antenna`；
- `intermittent visibility emitter POMDP unknown detection radius`。

本任务不执行该检索。Bishop 2010 若补读，只记录为 P2 future reading。

## E. 当前最值得实现的模型

### Minimal viable model

- 每频道 hard bearing polygon/curved set；全局使用 deterministic coverage route；发现后以 Zhao 几何生成第二点并用 worst-case diameter 选择；接近、光学、清除按题设状态机；Q4 对 no-signal 极保守。
- 最可能在比赛期完成、验证和解释，也是“确保全部清除”最容易建立证据链的方案。

### Enhanced model

- 在 hard set 上叠加 simulator-calibrated belief；Song-style high-mass components/ridges 调整全局路线，Dehghan-style one-step score 联合 information gain 与时间；Q4 用 factorized/particle belief 表示 $(x,y,\phi,R,\tau)$。
- 创新性较好，仍可通过消融实验与 MVP 对比，但必须保留 hard containment/coverage fallback。

### Too-complex-for-now model

- 20 频道、未知 existence、多源清除、5-D emitter state、连续动作和完整 observation scheduling 的高维 POMDP/online belief-tree search。
- 状态/观测/动作同时爆炸，且核心 directional likelihood 尚无直接文献支撑；目前只宜作为展望，不作为比赛主实现。

## 本轮受阻与不确定项

- Yang 2013 期刊全文 BLOCKED；authors/venue/pages/DOI 已核实，但 criterion、公式、定理、复杂度和验证细节不可作为已读正文结论。
- Dehghan 报告的是位置 RMSE（0.23 km vs 1.12 km），没有 path length / completion-time improvement；不能外推为 B 题总时间缩短。
- Song 的正文没有显式 no-signal update；将其概括成“probabilistic no-detection update”会过度陈述。
