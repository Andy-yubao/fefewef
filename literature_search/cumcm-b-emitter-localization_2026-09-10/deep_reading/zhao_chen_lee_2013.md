# Zhao, Chen & Lee (2013) 全文精读

## 元数据与证据边界

| 字段 | 内容 |
|---|---|
| 标题 | *Optimal Sensor Placement for Target Localisation and Tracking in 2D and 3D* |
| 作者 | Shiyu Zhao; Ben M. Chen; Tong H. Lee |
| 年份 / 载体 | 2013; *International Journal of Control*, 86(10), 1687–1704 |
| DOI | [10.1080/00207179.2013.792606](https://doi.org/10.1080/00207179.2013.792606) |
| 精读版本 | arXiv:1210.7397v1 的公开完整稿（2012-10-28）；25 页，包含期刊论文所需的定理、构造算法、梯度控制和数值实验 |
| 获取地址 | [arXiv 全文](https://arxiv.org/pdf/1210.7397) |
| 获取状态 | 完整预印本已获取并逐页核对；不是摘要替代品；本轮未另用早期会议短稿 |

标记约定：`[Paper]` 只表示预印本明确内容；`[B-inference]` 表示面向 B 题的适配。页码均指该 25 页公开稿。

## 1. Paper problem

- [Paper] 在二维或三维空间中，为一个目标配置 \(n\ge d\) 个同类传感器，使 Fisher 信息矩阵（FIM）尽可能各向同性，从而优化目标定位/跟踪精度（Abstract; Secs. I, III）。
- [Paper] 论文统一处理 range-only、bearing-only 与 RSS 三种同质传感器，但不处理混合传感器；传感器位置是设计变量，目标位置用一个粗略估计 \(p\) 代替（Sec. III-A, p.5）。
- [Paper] 主要贡献包括：加权几何的正规/非正规分类、全局最优条件、二维与 \(n=d+1\) 的显式构造、以及让移动传感器逼近最优几何的集中式梯度控制（Secs. IV–VI）。

## 2. Measurement model

- [Paper] 第 \(i\) 个传感器位置为 \(s_i\)，目标估计为 \(p\)，定义 \(r_i=s_i-p\)、距离 \(\|r_i\|\)、单位方向 \(g_i=r_i/\|r_i\|\)（Sec. III-A, p.5）。
- [Paper] 通用测量为 \(z_i=h_i(r_i)+v_i\)。bearing-only 的观测函数是单位方向向量 \(h_i(r_i)=r_i/\|r_i\|=g_i\)，即论文在局部高斯近似下使用向量式方位观测，而非 B 题的硬角扇区（Table I, Sec. III-A, p.5）。
- [Paper] bearing-only 的 FIM 为
  \[
  F=\sum_{i=1}^n c_i^2(I_d-g_i g_i^T),\qquad c_i=\frac{1}{\sigma_i\|r_i\|},
  \]
  （Table I, p.5）。这里距离和噪声标准差共同决定权重。
- [Paper] 为统一三类传感器，引入 \(G=\sum_i c_i^2g_i g_i^T\)。对 bearing-only，\(F=(\sum_i c_i^2)I_d-G\)；对 range/RSS，\(F=G\)（Sec. III-B, Eqs. (8)–(9), pp.6–7）。

## 3. Noise / uncertainty

- [Paper] 噪声 \(v_i\) 为零均值高斯，协方差 \(\Sigma_i=\sigma_i^2I_m\)，不同传感器噪声不相关（Sec. III-A, p.5）。FIM 通式见 Eq. (6)。
- [Paper] bearing-only 与 RSS 的权重随距离衰减。为避免把传感器无限移近目标导致平凡最优，论文在这两种情形固定距离和噪声方差；range-only 的权重与距离无关（Sec. III-A, p.5）。
- [B-inference] B 题给的是确定性 \(\pm1^\circ\) 硬界，且同地点重复误差相同。把 \(1^\circ\) 直接当独立高斯标准差会改变证据语义；若使用 FIM，只能作为点估计附近的几何代理，不应声称得到题设下的置信概率或硬保证。

## 4. State / feasible-set representation

- [Paper] 论文状态是单一目标点估计 \(p\) 与相对几何 \((g_i,\|r_i\|)\)，不维护目标可行集合（Sec. III-A, p.5）。
- [Paper] 所有观测对精度的作用压缩到 \(F\) 或 \(G\)；方向向量位于单位球面，系数 \(c_i\) 表示不同传感器的信息权重（Sec. III）。
- [Paper] 传感器运动模型为 \(\dot s_i=u_i\)，分析梯度律时把 \(p\) 视为固定，且投影控制保持各 \(\|r_i\|\) 不变（Sec. VI, Eqs. (28)–(29), pp.19–20）。
- [B-inference] 第一观测后的 B 题状态是一个扇区/多边形，而不是 \(p\)。若用本论文，需要另选中心、Chebyshev 中心或最坏情形采样点，并对这个降维近似单独验证。

## 5. Objective

- [Paper] 经典 D-optimal 目标是最大化 \(\det F\)；论文为获得更易分析的几何条件，提出
  \[
  \min\|F-\bar\lambda I_d\|_F^2,
  \]
  其中 \(\bar\lambda=\operatorname{tr}(F)/d\) 是平均特征值（Problem 3.1, Eq. (7), p.6）。这等价于最小化 \(\|G\|_F^2\) 加常数（Eqs. (8)–(9), pp.6–7）。
- [Paper] Lemma 3.4 给出 \(\det F\le\bar\lambda^d\)，等号当且仅当 \(F=\bar\lambda I_d\)（Eqs. (10)–(12), pp.7–8）。二维中异方差目标与 D-optimal 通过 \(\|F-\bar\lambda I_2\|_F^2=-2\det F+2\bar\lambda^2\) 精确等价；三维只有当各向同性可实现时，两者共同达到理想最优。
- [Paper] 目标只评价信息几何，没有行驶距离、观测 5 s、频道切换、清除时间、检测失败或可行区域直径。

## 6. Main theorem / proposition / closed-form

- [Paper] 假设系数按 \(c_1\ge\cdots\ge c_n>0\) 排序。irregularity \(k_0\) 是满足
  \[
  c_{k+1}^2\le\frac{1}{d-k}\sum_{i=k+1}^n c_i^2
  \]
  的最小非负 \(k\)，且 \(0\le k_0\le d-1\)（Definition 2.1, Eq. (4), p.3）。\(k_0=0\) 为 regular，等价于 \(\max_jc_j^2\le d^{-1}\sum_i c_i^2\)（Eq. (5), p.3）。这里 regular/irregular 指权重序列，不是目测阵形是否规则。
- [Paper] Theorem 4.1：regular 时
  \[
  \|G\|_F^2\ge\frac1d\Big(\sum_i c_i^2\Big)^2,
  \]
  等号当且仅当 \(\sum_i c_i^2g_i g_i^T=d^{-1}(\sum_i c_i^2)I_d\)，即形成加权 tight frame（Eqs. (13)–(14), pp.9–10）。
- [Paper] Theorem 4.3：irregularity 为 \(k_0\) 时，下界为
  \[
  \sum_{i=1}^{k_0}c_i^4+rac{1}{d-k_0}\Big(\sum_{i=k_0+1}^n c_i^2\Big)^2,
  \]
  且最强的 \(k_0\) 个方向彼此正交，其余方向在正交补空间中构成 regular 最优配置（Eqs. (15)–(16), pp.10–11）。
- [Paper] Theorem 4.4：当 \(n=d\) 时，\(\|G\|_F^2\ge\sum_i c_i^4\)，等号当且仅当 \(g_1,\ldots,g_d\) 构成正交基（p.12）。因此二维恰有两个 bearing-only 传感器且各自距离/噪声权重固定时，最优相对方位夹角为 \(90^\circ\)，即使两权重不相等也成立。
- [Paper] 这个 \(90^\circ\) 结论以目标点 \(p\)、同时的局部高斯 FIM、固定 \(c_i\) 为条件；它不是第一条硬界方位扇区上的鲁棒闭式第二点解。

## 7. Algorithm

### 二维显式构造

- [Paper] 令 \(g_i=[\cos\theta_i,\sin\theta_i]^T\)，再令 \(\bar g_i=[\cos2\theta_i,\sin2\theta_i]^T\)。Lemma 5.1 把二维 tight-frame 条件化为 \(\sum_i c_i^2\bar g_i=0\)（Eq. (18), p.13）；Theorem 5.2 证明其可实现当且仅当 regular 条件 \(\max_jc_j^2\le\frac12\sum_i c_i^2\) 成立（Eq. (19), p.13）。
- [Paper] Algorithm 1（p.14）是显式的二维最优构造：在已排序权重中找累计和跨过总权重一半的索引 \(n_0\)，形成三段长度 \(\ell_1,\ell_2,\ell_3\)（Eqs. (20)–(21)）；由这三边构造三角形内角 \(\alpha_{12},\alpha_{13}\)；将三组 \(g_i\) 分别放在角度 \(0\)、\((\pi+\alpha_{12})/2\)、\((\pi-\alpha_{13})/2\)。这回答了“是否有显式摆放算法”：有，而且不必借助较短会议稿。

### \(n=d+1\) 与移动梯度法

- [Paper] Algorithm 2（p.16）对唯一的 regular \(n=d+1\) 情形，用权重计算辅助向量，对其做 SVD/取正交补，再按列缩放构造最优 \(g_i\)。
- [Paper] Sec. VI 定义势函数 \(V=\frac14(\|G\|_F^2-\beta)\)，采用
  \[
  \dot r_i=-P_iGg_i,\qquad P_i=I_d-g_i g_i^T
  \]
  （Eq. (28), pp.19–20）。Eq. (29) 证明距离保持不变；Proposition 6.1 证明轨迹收敛到临界集合 \(E=\{P_iGg_i=0,\forall i\}\)（pp.20–21）。
- [Paper] 收敛到临界集合不等于从任意初值全局收敛到最优；论文明确指出 \(E\) 也含鞍点和最大点，局部稳定域仍需研究（Sec. VI, p.21）。控制律集中式依赖全局 \(G\)，不是分布式保证。

## 8. Complexity

- [Paper] 论文没有为 Algorithms 1–2 或连续梯度流给出 Big-O 复杂度，也没有给梯度法达到给定误差所需的迭代上界。
- [B-inference] Algorithm 1 在权重已排序时，找 \(n_0\) 与赋方向是 \(O(n)\)；若先排序则为 \(O(n\log n)\)。
- [B-inference] Algorithm 2 的主要计算是尺度约为 \(d\) 的 SVD，若把维数视作变量约为 \(O(d^3)\)；论文只用 \(d=2,3\)。
- [B-inference] 梯度离散化每步形成 \(G\) 约需 \(O(nd^2)\)，但总步数和通信成本无理论界；把它用于机器人路径还需碰撞、可达域和时间离散化。

## 9. Validation

- [Paper] 验证是数值仿真，不是实测定位误差实验，也没有把传感器几何接入一个实际目标估计器。
- [Paper] Figs. 9–10 展示三维 regular 与 irregular 配置的梯度演化，目标误差趋近理论下界（Sec. VI, pp.21–23）。
- [Paper] Scenario 1 针对 bearing-only/RSS，固定各传感器距离并设置相同噪声方差，覆盖二维/三维、不同 \(n\) 和 \(k_0\)；二维两传感器例子的最终夹角为 \(90^\circ\)（pp.21–23）。
- [Paper] Scenario 2 为 2 架 UAV 与 2 台地面机器人围绕目标的 range-only 配置，加入高度势函数，数值误差也逼近下界（pp.23–24）。
- [Paper] 没有与最坏情形集合面积/直径、旅行时间或一次/多次序贯选点基线比较。

## 10. What transfers to CUMCM B（Q1–Q4）

- [B-inference][Q2] 最有价值的可迁移结构是“交叉方位应提供互补方向信息”。若第一观测点为 \(s_1\)，已有可信点代理 \(p\)，第二点可优先放在穿过 \(p\) 且与 \(p-s_1\) 垂直的方向上，并在题设允许的接收距离与可达域内选择半径。该 \(90^\circ\) 只对点代理和固定权重成立。
- [B-inference][Q2] 距离/噪声权重不能忽略：bearing-only 中 \(c_i=1/(\sigma_i\|r_i\|)\)。恰有两点且两距离已固定时，权重不改变正交角；若第二点距离也是决策变量，论文主动把距离固定以避免趋近目标的平凡解，因此不能给出 B 题最优距离。
- [B-inference][Q2] 对第一观测后的集合 \(U_1\)，可把 Zhao 几何变成候选生成器：对 \(U_1\) 的代表点或多个场景生成近正交候选点，再用 B 题硬界可行集的最坏面积/直径筛选，而不是直接以 FIM 排名定案。
- [B-inference][Q1] FIM 的各向同性可作“避免两条方位线近乎平行”的解释，但 P1 的最终区域仍应按硬扇区求交。
- [B-inference][Q3] 对已建立点估计的单个全向源，可用 FIM 指导追加测点；未知源数量、关联与搜索未覆盖。
- [B-inference][Q4] 若定向源的位置与朝向已有局部估计，可在增广状态上重建 Jacobian/FIM；原文没有该模型，因此只可作为待验证延伸。

## 11. What does NOT transfer

- [Paper] 论文假设高斯噪声、独立观测和局部点估计；[B-inference] B 题是非概率硬界且同地点误差重复不变，不能把 CRLB 当可行区域保证。
- [Paper] 传感器布置是围绕给定 \(p\) 的同时几何；[B-inference] B 题第二点是在第一读数后序贯决定，目标仍是集合，第二读数也尚未知。
- [Paper] bearing/RSS 距离被固定；[B-inference] B 题有 1000–1500 m 接收范围、1800 m 区域、5 m/s 运动与测量耗时，最优距离/路线由这些约束共同决定。
- [Paper] 梯度律保持半径、连续运动、集中式获得所有方向；[B-inference] 它不是具有离散观测、频道切换和清除动作的完整机器人策略。
- [Paper] 文中不处理漏检、无信号负信息、未知目标数、多个频道、定向覆盖或任务终止。

## 12. Concrete modeling implications A / B / C

### A. 可以直接借用的公式 / 定理 / 算法

- 在“目标近似为一点、两次观测权重/距离固定”的局部子问题中，把两条目标—观测点方向尽量设计为正交；引用 Theorem 4.4 时同时写清这些条件。
- 把 \(c_i=1/(\sigma_i r_i)\) 作为解释方位观测随距离变弱的权重形式，但不把它冒充题设给定规律。

### B. 可以借用的结构，但必须改 measurement model

- 以正交几何生成第二点候选，再用 B 题的硬界扇区交，对第一可行集中的真值与所有可能误差做最坏情形面积、直径或成功率评价。
- 比较两条路线：硬界集合最小化作为主方案；FIM/D-optimal 作为计算便宜的基线或候选预筛，并通过仿真检验二者排名的一致性。
- 若需要多观测点固定编队，可用 weighted tight frame 和 Algorithm 1 构造二维基准阵形，再加入可达性、边界与时间成本。

### C. 只能作为理论背景，不能进入核心算法

- 不用本论文声称硬界 \(\pm1^\circ\) 下第二点全局最优、任何第一扇区上都应机械取 \(90^\circ\)，或梯度律能全局收敛。
- 不用 CRLB/FIM 代替未知数量搜索、无信号排除、频道调度、定向覆盖和清除逻辑。
