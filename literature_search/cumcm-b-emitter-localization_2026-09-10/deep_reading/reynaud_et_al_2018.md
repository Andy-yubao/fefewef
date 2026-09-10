# Reynaud et al. (2018) 全文精读

## 元数据与证据边界

| 字段 | 内容 |
|---|---|
| 标题 | *A Set-Membership Approach to Find and Track Multiple Targets Using a Fleet of UAVs* |
| 作者 | Sébastien Reynaud; Michel Kieffer; Hélène Piet-Lahanier; Léon Reboul |
| 年份 / 载体 | 2018; *2018 IEEE Conference on Decision and Control (CDC)*, 484–489 |
| DOI | [10.1109/CDC.2018.8619672](https://doi.org/10.1109/CDC.2018.8619672) |
| 精读版本 | HAL 公开作者稿；PDF 共 7 页，第 1 页是 HAL 封面，正文 article pp.1–6 对应 PDF pp.2–7 |
| 获取地址 | [HAL 记录](https://hal.science/hal-01994781)；当前原站下载触发反机器人页，精读使用其公开文件的 [Internet Archive 存档快照](https://web.archive.org/web/20231206061635id_/https://hal.science/hal-01994781v1/file/DTIS18250.1540913569.pdf) |
| 获取状态 | 完整作者稿已获取并逐页核对；不是摘要替代品 |

标记约定：`[Paper]` 是文章明确内容；`[B-inference]` 是面向 CUMCM B 题的改造。定位以“PDF p.x / article p.y”标注。

## 1. Paper problem

- [Paper] 论文让 \(N_U\) 架 UAV 搜索并跟踪数量未知、初始位置未知的 \(N_T\) 个目标；目标数虽以符号存在，但算法事先不知道其值（Sec. II, PDF p.3 / article p.2）。
- [Paper] UAV 既要缩小已发现目标的集合估计，也要缩小“仍可能存在未发现目标”的区域；两项共同进入一步贪心控制目标（Secs. II-C, IV）。
- [Paper] 多 UAV 之间可通信集合信息，并通过集合交收紧估计；算法采用 bounded-error / set-membership，而非概率滤波（Secs. III, V）。

## 2. Measurement model

- [Paper] UAV 与目标离散动力学为
  \[
  r_{i,k+1}=f_k^R(r_{i,k},u_{i,k}),\qquad
  z_{j,k+1}=f_k^Z(z_{j,k},v_{j,k}),
  \]
  其中 \(u_{i,k}\in\mathcal U\)，目标扰动 \(v_{j,k}\in[v_k]\) 为已知区间盒；所有目标初态落在紧集 \(\mathcal Z_0\)（Eqs. (1)–(2), Sec. II-A, PDF p.3 / article p.2）。
- [Paper] UAV \(i\) 在状态 \(r_{i,k}\) 时的传感覆盖是紧集 \(\mathcal F_i(r_{i,k})\)。检测语义是精确双向等价
  \[
  j\in\mathcal L_{i,k}\iff z_{j,k}\in\mathcal F_i(r_{i,k}),
  \]
  即覆盖内必检出、覆盖外不检出，没有虚警或漏检（Eq. (3), Sec. II-B, PDF p.3 / article p.2）。
- [Paper] 对已检出的目标，UAV 获得
  \[
  y_{i,j,k}=h_i(r_{i,k},z_{j,k})+w_{i,j,k},\qquad w_{i,j,k}\in[w_k],
  \]
  即非线性观测加未知但有界噪声盒（Eq. (4), 同页）。
- [B-inference] B 题的“收到信号后得到 \(\pm1^\circ\) 示向”可替换 \(h_i\) 的位置观测；但检测覆盖属于发射源且接收半径未知，不能原样使用已知的 \(\mathcal F_i(r)\)。

## 3. Noise / uncertainty

- [Paper] 过程扰动与测量误差只要求落在已知 interval vectors \([v_k]\)、\([w_k]\) 中，没有分布和独立性要求（Sec. II）。
- [Paper] 算法通过外逼近集合保证真状态不会在满足边界条件时被删掉；实际实现以 interval analysis 处理非线性像与逆像（Sec. V-A, PDF p.6 / article p.5）。
- [Paper] 检测本身却是无误差的 Eq. (3)。若现实存在漏检，基于 no-detection 的集合删除就会失去包含保证；论文没有为检测误差加松弛变量。
- [B-inference] B 题同地点系统性示向误差可自然放入有界角区间；而信号有无必须依据题设分别建立“必收、可能收、不可能收”区域，不能假装成精确已知 FoV。

## 4. State / feasible-set representation

- [Paper] 对 UAV \(i\)，\(\mathcal D_{i,k}\) 是已发现目标索引集合；\(\mathcal Z_{i,k}=\{Z_{i,j,k}\}_{j\in\mathcal D_{i,k}}\) 是各已发现目标的集合估计（Sec. II-C, PDF p.3 / article p.2）。
- [Paper] \(\overline Z_{i,k}\) 是“尚未发现目标仍可能处于的状态值集合”。它是状态空间中的未搜索区域，可同时容纳零个、一个或多个目标；它不是目标数量的概率分布或集合基数区间。初始化为 \(\mathcal D_{i,0}=\varnothing\)、\(\mathcal Z_{i,0}=\varnothing\)、\(\overline Z_{i,0}=\mathcal Z_0\)（Sec. II-C）。
- [Paper] 已知目标集与未知目标区域都用 subpavings 表示，即互不重叠 interval vectors 的并；这种表示允许非凸和不连通集合（Sec. V-A, PDF p.6 / article p.5）。
- [B-inference] 对 B 题可为每个频道维护已定位源集合与未排除联合状态区；若源朝向未知，状态至少要扩展为 \((x,y,\psi)\)，并可能加入接收半径/类型。

## 5. Objective

- [Paper] 单 UAV 指标为
  \[
  \Phi(\mathcal Z_{i,k},\overline Z_{i,k})=
  \frac{1}{\max\{1,|\mathcal D_{i,k}|\}}
  \sum_{j\in\mathcal D_{i,k}}\phi(Z_{i,j,k})+
  \alpha\phi(\overline Z_{i,k}),
  \]
  其中 \(\phi\) 是集合体积，\(\alpha\) 权衡跟踪与搜索（Eq. (5), PDF p.3 / article p.2）。
- [Paper] 全队指标是各 UAV 指标平均 \(\Phi_k=N_U^{-1}\sum_i\Phi(\mathcal Z_{i,k},\overline Z_{i,k})\)（Eq. (6), 同页）。
- [Paper] 控制采用一步贪心：从允许动作中选使下一时刻指标最小的动作（Eq. (15), PDF p.4 / article p.3）。因为未来观测未知，后续 Eqs. (16)–(27) 构造可在行动前计算的体积上界。
- [Paper] 目标未包含总任务时间、能耗、频道切换、目标清除或误报/漏报代价。

## 6. Main theorem / proposition / closed-form

- [Paper] 论文没有给出类似全局最优或竞争比的主定理；关键可验证性质来自集合递推和上界。
- [Paper] 预测：对每个已发现目标及未发现区域，取动力学在有界扰动下的直接像（Eqs. (7)–(8), Sec. III-A, PDF pp.3–4 / article pp.2–3）。
- [Paper] 正观测校正：已知目标再次检测时，用预测集与测量逆像相交（Eq. (10), PDF p.4 / article p.3）；新发现目标的初始集合是未发现预测区与测量逆像的交（Eq. (11)）。
- [Paper] 负观测校正：已发现目标若未被看到，从其预测集减去当前 FoV（Eq. (12)）；对未知目标区域执行
  \[
  \overline Z_{i,k+1|k+1}=overline Z_{i,k+1|k}\setminus\mathcal F_i(r_{i,k+1})
  \]
  （Eq. (14), PDF p.4 / article p.3）。这正是 no-detection / negative information 的数学落点。
- [Paper] 多 UAV 通信时合并已发现索引，并对相同目标集合求交；若一方尚未见过该目标，则用另一方的已发现目标集合与其 \(\overline Z\) 相交；各自未发现区域也求交（Sec. III-C, PDF p.4 / article p.3）。
- [Paper] Eq. (26) 给出下一步 \(\Phi\) 的可计算上界，把“已知目标可能看到/看不到”的最坏体积项、新发现目标项和下一未发现区域体积组合起来；Eq. (27) 用候选位置的 FoV 集合差更新未发现区域（Sec. IV-A, PDF pp.4–5 / article pp.3–4）。
- [Paper] 多 UAV 一步联合控制为对 \(\mathcal U^{N_U}\) 上的全队下一步指标最小化（Eq. (28), PDF p.6 / article p.5）。文章也允许各 UAV 独立求解，或由 leader 广播联合动作。

## 7. Algorithm

论文没有编号伪代码；按 Eqs. (7)–(28) 可还原为以下循环：

1. [Paper] 初始化：所有已发现集合为空，\(\overline Z=\mathcal Z_0\)（Sec. III 开头, PDF p.3 / article p.2）。
2. [Paper] 预测：用 ImageSp 等外逼近算子传播各 \(Z_j\) 和 \(\overline Z\)（Eqs. (7)–(8); Sec. V-A）。
3. [Paper] 候选动作评价：对每个 \(u\in\mathcal U\)，计算 Eq. (26) 上界及 Eq. (27) 候选未搜索区；选一步指标最小者（Eq. (15)）。多 UAV 可按 Eq. (28) 联合枚举。
4. [Paper] 移动并传感：得到检测索引 \(\mathcal L\) 与有界观测 \(y\)。
5. [Paper] 校正：按 Eqs. (10)–(11) 使用正观测逆像相交，按 Eqs. (12)、(14) 使用未检测信息做集合差，更新 \(\mathcal D\)（Eq. (13)）。
6. [Paper] 通信：共享 \(\mathcal D,\mathcal Z,\overline Z\)，按 Sec. III-C 求集合交。
7. [Paper] 重复；仿真把 \(\overline Z\) 为空作为“已搜索完全部初始区域”的终止依据（Sec. V-B, PDF p.7 / article p.6）。

[Paper] 这是一步滚动/greedy，而不是有限时域 MPC；文章没有给出全局任务完成时间最优性。

## 8. Complexity

- [Paper] 文章没有报告渐近复杂度、分支盒数量上界或实时耗时。
- [Paper] 集合运算采用 interval subpavings；ImageSp 外逼近直接像，SIVIA 外逼近逆像与集合差，体积为各互不重叠盒体积之和（Sec. V-A, PDF p.6 / article p.5）。
- [B-inference] 区间细分在状态维数和精度提高时可能产生指数级盒数，这是将状态扩展到位置、朝向、半径时的主要计算瓶颈。
- [B-inference] 若每架 UAV 有 \(q=|\mathcal U|\) 个离散动作，单 UAV 每步需约 \(q\) 次候选集合运算；Eq. (28) 直接联合枚举为 \(q^{N_U}\)。B 题单机器人可消除这一多智能体组合爆炸。

## 9. Validation

- [Paper] MATLAB/Intlab 仿真有 3 个静态目标、2 架 UAV、500 m × 500 m 区域，\(\alpha=1\)（Sec. V-B, PDF p.7 / article p.6）。
- [Paper] UAV 高度 75 m，光学 FoV 为方形底面的视锥，方位/俯仰半角均 \(\pi/8\)；目标位置测量误差在各坐标上为 \(\pm5\) m（同处）。
- [Paper] UAV 速度 15 m/s，采样周期 1 s；每步动作集合含 20 个在 \([-\pi/2,\pi/2]\) 均匀分布的航向变化；每时刻通信，控制以各 UAV 独立方式计算（同处）。
- [Paper] 图示中 3 个目标依次检出，算法持续到 \(\overline Z\) 为空；约 100 次迭代内 \(\Phi\) 从约 \(2.4\times10^5\) 降到 \(0.8\times10^5\)，已发现目标集合体积低于 100 m²（Figs. 1–2, PDF p.7 / article p.6）。
- [Paper] 只有单场景示范，没有统计重复、基线、真实飞行、漏检实验、运行时间或最优性差距。

## 10. What transfers to CUMCM B（Q1–Q4）

- [B-inference][Q3] 最直接的结构是“已发现目标集合 + 未发现目标仍可能存在的区域”。未知数量不必先估一个 \(N_T\)：只要未搜索区非空，就仍可能存在新源；检测到新频道/新源时新增一个集合状态。
- [B-inference][Q3] 单机器人化后，可删去队伍平均 Eq. (6)、通信融合 Sec. III-C 和联合动作 Eq. (28)，保留“预测—候选动作—观测—正/负校正—终止”的一步滚动链。静态发射源令预测步骤近似恒等。
- [B-inference][Q3] 对全向源，正信号加入方位扇区与距离一致约束；无信号的排除必须保守。若单源接收半径未知但在 1000–1500 m，则距离小于 1000 m 是题设保证接收的区域，可由无信号排除；1000–1500 m 环带只能标为“可能接收”，不能仅凭无信号全部删掉。
- [B-inference][Q3] 若按频道逐个处理，\(\overline Z_c\) 可表示频道 \(c\) 尚可能存在未发现源的位置；频道切换 1 s、示向 5 s、移动时间必须加入候选动作代价，替代原文只最小化集合体积的 Eq. (15)。
- [B-inference][Q4] 可把联合状态写成 \(\xi=(x,y,\psi,R,\tau)\)，其中 \(\psi\) 是方向、\(R\) 是接收半径、\(\tau\) 是全向/定向类型。正/负观测在联合状态空间中做交与差，形式上继承 set-membership 链。
- [B-inference][Q4] 但位置投影上的 no-signal 很弱：对某位置，未知朝向可能总能让扇区背离机器人。只有在联合 \((x,y,\psi)\) 空间中，才能排除“机器人同时处于距离范围和发射扇区内”的那些状态；不能据此直接排除该位置的所有朝向。

## 11. What does NOT transfer

- [Paper] Eq. (3) 假设传感器 FoV 已知且覆盖内必检测；[B-inference] B 题接收半径为每个发射源的未知 1000–1500 m，Q4 发射朝向也未知，FoV 是目标状态的一部分而非已知机器人传感器几何。
- [Paper] 被检出目标直接返回带 \(\pm5\) m 位置误差的观测；[B-inference] B 题返回方位，单次观测不能形成紧位置盒。
- [Paper] 目标索引在检测集合 \(\mathcal L\) 中可识别；[B-inference] B 题虽有 20 个频道，但同频道是否唯一对应一个源、如何区分同频道多源必须以题面/模拟器为准，不能由本文补设。
- [Paper] \(\overline Z=\varnothing\) 在精确检测模型下表示初始区域被穷尽；[B-inference] 若存在未知覆盖或频道未监听，这一终止条件不成立。
- [Paper] 没有清除动作；[B-inference] B 题定位后还需到 20 m 光学确认、3 s 检测、2 s 清除，清除会改变后续信号状态，必须加入状态机。
- [Paper] 一步指标没有总时长保证；[B-inference] 不能据此声称 B 题机器人完成全部任务时间最短。

## 12. Concrete modeling implications A / B / C

### A. 可以直接借用的公式 / 定理 / 算法

- 为每个频道维护：已发现源的有界定位集、尚可能存在未发现源的区域、已确认/已清除状态；每次观测都记录正信息和负信息。
- 采用一步滚动决策，每次根据当前集合状态重算候选下一动作；单机器人不保留通信和联合控制。

### B. 可以借用的结构，但必须改 measurement model

- 把原文已知 FoV 改为 B 题的三值接收模型：必接收区、可能接收区、必不接收区；负信息只删除“在所有允许参数下本应接收”的联合状态。
- Q3 静态全向源可将预测简化为恒等映射，把观测逆像换成角扇区；候选动作目标加入移动、切频、示向、光学和清除时间。
- Q4 在位置—朝向联合空间保留集合运算；只有经过联合状态投影验证后，才更新位置层未搜索区。

### C. 只能作为理论背景，不能进入核心算法

- 不直接采用 Eq. (3) 的无漏检语义、不把一次无信号当成完整 FoV 清空，也不把 \(\overline Z\) 的体积当作未知源数量。
- 不引用该单场景仿真证明算法实时、全局最优或必在有限时间找到并清除所有 B 题发射源。
