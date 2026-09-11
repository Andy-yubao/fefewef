# Song, Kim & Yi 2012 全文精读

## 元数据与证据边界

- [Paper] Dezhen Song, Chang-Young Kim, Jingang Yi, *Simultaneous Localization of Multiple Unknown and Transient Radio Sources Using a Mobile Robot*, **IEEE Transactions on Robotics**, vol. 28, no. 3, pp. 668-680, June 2012, DOI `10.1109/TRO.2012.2183069`。所读为作者主页公开的 13 页全文。
- provenance: **post-Round-1 teammate-supplied supplemental anchor**；不是 Round 1 检索命中。
- [Paper] 下述引用同时给 PDF 页与 printed page。本文处理时间间歇的全向 radio sources、机器人上的定向接收天线和 RSS；不处理发射源定向覆盖。

## 1. Paper problem

- [Paper] 一只已知自身位姿的 mobile robot，在无障碍二维空间定位多个数量未知、身份不可辨、静止、短时且间歇发射的 radio sources（Sec. I, PDF p.1 / p.668；Sec. III-B, PDF p.3 / p.670）。
- [Paper] source transmission pattern 未知；轻载网络下把“两个传输恰好同时开始”的概率忽略。为建模搜索时间，Sec. VI-B 另假定每个源按独立 Poisson process 发射（PDF p.7 / p.674）。
- [Paper] 发射源均假设同功率、omnidirectional；机器人配 fixed directional antenna，输入为 antenna orientation 对应的离散 RSS（Sec. III-A/B, PDF pp.2-3 / pp.669-670）。
- [Paper] source identity anonymous，单次信号不能与特定源关联；目标不是显式估计每个 source identity，而是让占据概率在含源 cells 上收敛。

## 2. Measurement model

- [Paper] cell (i) 到机器人距离和相对 bearing 为 Eqs. (2)-(3)。expected RSS 为
  \[
  s_i=c(d_{ij}^k)^{-\beta}\varphi(\phi_{ij}^k),
  \]
  dBm 均值 (\mu_i) 见 Eq. (5)（Sec. IV-A, PDF p.4 / p.671）。
- [Paper] 实物 HyperGain HG2415G antenna 的 pattern 用分段 $\cos^2(4\phi)$ 等函数拟合，参数 $c=63.09,\beta=2.53$；RSS 条件分布近似 Gaussian，校准得 $\sigma=3.3$（Eqs. (6)-(10), PDF pp.4-5 / pp.671-672）。

## 3. Noise / uncertainty

- [Paper] RSS 随 transmission uncertainty、receiver resolution 和 background noise 变化，离散读数由 Gaussian density 在整数 bin 上积分/近似得到（Eqs. (7)-(10), PDF p.4 / p.671）。
- [Paper] transient 指 time-domain 中短时、动态、间歇 transmission；不是 source motion，也不是 spatial directional coverage。

## 4. State / feasible-set / belief representation

### SPOG = Spatiotemporal Probability Occupancy Grid

- [Paper] 将区域划分为 $n$ 个等大方格。$C_i$ 表示 cell $i$ 至少含一个源，$P(C_i)$ 是 spatial occupancy probability；cell size 由 RSS resolution 的 $2\sigma$-separation rule 决定（Sec. III-C, Eqs. (12)-(13), PDF pp.3,5 / pp.670,672）。
- [Paper] 在检测到传输的时刻，(C_i^1) 表示 cell (i) 是 active source，(C_i^0) 表示 inactive，且
  \[
  P(C_i^0)+P(C_i^1)=1,\qquad \sum_iP(C_i^1)=1,
  \]
  因轻载、无碰撞假设一次只存在一个 active transmission（Eq. (1), PDF p.3 / p.670）。$P(C_i^1)$ 由 relative transmission rate 决定，是 temporal component。
- [Paper] 多个源通过多个 cells 的 $P(C_i)$ 同时趋近 1 表示；$\sum_iP(C_i)$ 在正确收敛时等于含源 cell 数。模型估的是 occupied cells，不显式给独立 source-count random variable，也不解决同 cell 多源计数（Sec. III-C）。
- [Paper] 初始值为 $P(C_i\mid Z_0^0)=0$、$P(C_i^1\mid Z_0^0)=1/n$（Algorithm 1 discussion, PDF p.7 / p.674）。这不是标准“非零 occupancy prior”，而是其递推初始化约定。

### Positive detection update

- [Paper] 对 RSS (Z_j^k=z)，先用 Bayes 更新 active cell：
  \[
  P(C_i^1|Z=z)=\frac{P(Z=z|C_i^1)P(C_i^1)}{\sum_sP(Z=z|C_s^1)P(C_s^1)},
  \]
  见 Eq. (15)（PDF p.5 / p.672）。
- [Paper] 再利用 event decomposition 和 active/source independence 得 occupancy update Eq. (17)，并将全部历史 (Z^-(Z_j^k)) 加入条件，形成递归 Eqs. (19)-(20)（Sec. IV-C, PDF pp.5-6 / pp.672-673）。这是 SPOG 的核心。

### No signal / no detection

- [Paper] **论文没有把“监听一段时间却未收到信号”作为显式 negative observation 写进 Eqs. (19)-(20)。** Algorithm 1 在检测到 radio signal 时运行；若当前没有传输，SPOG 不因一个 `no signal` 事件做空间排除（Sec. III-D, Sec. VI-A, PDF pp.3,7 / pp.670,674）。
- [Paper] 时间间歇通过 active probability / transmission rate 以及 Sec. VI-B 的 Poisson waiting-time 分析体现，而非用一次未检测到信号删除 cell。
- [B-inference] 因此 Song 比 Reynaud 更自然地提醒“no signal 不等于 source absent”，但它并没有提供可直接抄用的 B 题 no-signal likelihood；B 题仍需自行定义 $P(\mathrm{no\ signal}\mid x,y,\phi,R,\tau,a)$。

## 5. Objective

- [Paper] 理想瞬时配置欲最大化目标 cell posterior；Eqs. (21)-(24) 将其化为 likelihood-ratio minimization。但 future RSS (z) 未知，global nonlinear optimum 不可直接求（Sec. V, PDF p.6 / p.673）。
- [Paper] Lemma 1 证明机器人位于 cell center 时，对任意 future reception (z)，相应 likelihood ratio 是局部极小；由此导出“走向高 occupancy cells”的 ridge walking heuristic（PDF pp.6,13 / pp.673,680）。

## 6. Main theorem / proposition / closed-form

- [Paper] Definition 1：若 $P(C_i\mid Z)\ge p_t$，认为至少一个源定位到 cell $i$（PDF p.4 / p.671）。这是 probabilistic threshold，不是 hard guarantee。
- [Paper] Theorem 1 给出单个 Poisson source 的 expected search time 上界 Eq. (31)；Remark 2 指其形式不含 source 总数，因此单源发现时间对源数不敏感（Sec. VI-B, PDF pp.7-9 / pp.674-676）。该结论依赖 Poisson、repeated tour、sensing circle 与近似条件，不等同于“找完全部源的时间与数量无关”。

## 7. Algorithm

### Ridge Walking Algorithm (RWA)

- [Paper] 对 threshold (p) 定义 level set
  \[
  L(p)=\{i:P(C_i|Z)\ge p\},
  \]
  并分成 disconnected components (L_l)（Eq. (26), PDF p.7 / p.674）。
- [Paper] 每个 component 的 ridge $R_l$ 定义为该 component 内最远两点连成的线段（Eq. (27)）；这不是 density 的微分几何 ridge，也不是逐步 greedy 到最大格点。
- [Paper] on-ridge movement 用于穿越高概率区且使定向接收天线沿 ridge；off-ridge movement 连接各 ridge。把每条必走 ridge edge 压成 super-vertex，解改造的 Euclidean TSP；off-ridge 走最短路且用最高速度（Sec. V, PDF p.7 / p.674）。
- [Paper] 固定 planning period $\tau_0$ 内，可用于 on-ridge 的时间为 $t_{ON}=\tau_0-d_{OFF}/v_{max}$；按各 component occupancy mass 比例分配 $\tau_l$（Eqs. (28)-(29)）。
- [Paper] RWA 初期在 (L(p)=\varnothing) 时 random walk；正常阶段周期性重算 ridges/TSP；连续 (k_{max}) 个 period 未发现新源即停止（Algorithm 2 discussion, PDF p.7 / p.674）。

## 8. Complexity

- [Paper] SPOG update Algorithm 1 为 $O(n^2)$（每个 cell 对全部 cells 计算 mixture/update）；用 MST 近似 Euclidean TSP 时，RWA 为 $O(n+l_{max}^2)$（Sec. VI-A, PDF p.7 / p.674；Conclusion, PDF p.11 / p.678）。
- [B-inference] B 题若为每个频道单独维护二维 grid，朴素成本会再乘 active channel 数；若扩展到 $(x,y,\phi,R,\tau)$ 的 dense grid，cell 数呈维数乘法增长，$O(n^2)$ update 会迅速失控。

## 9. Validation

- [Paper] antenna 以 328 个配置、6560 次 readings 校准；实现使用 Visual C++/.NET 2005，硬件为 2.13 GHz Core 2 Duo / 2 GB RAM（Sec. VII, PDF p.9 / p.676）。
- [Paper] hardware-driven simulation 使用 $50\times50$ grid、5.08 cm cell、独立同分布 Poisson rate $0.012$ packet/s、$p_t=0.8$。源数 2-10，每个设置 10 trials；$\tau_0=800$ s 时 RWA 最佳，并与 random walk、fixed-route patrol 比较，图示 localization time consistently shorter（Fig. 6, PDF pp.9-10 / pp.676-677）。论文未在正文表格给出统一百分比改进。
- [Paper] physical experiment 为 $10\times10$ m、$50\times50$ grid、3 个 XBee sources、rate $0.05$ packet/s、$\tau_0=160$ s；机器人最高 0.4 m/s，外部视觉位姿精度位置 ±5 cm、朝向 ±3.5°，成功定位 3 源（Fig. 7, PDF p.10 / p.677）。

## 10. What transfers to CUMCM B（Q1-Q4）

- [B-inference][Q3] B 题每源频道互异，因此 `channel = source identity label`，可删除 Song 最困难的匿名 data association。可为每频道定义 existence $E_c\in\{0,1\}$ 与 conditional location belief $p(x_c,y_c\mid H,E_c=1)$。
- [B-inference][Q3] Song 支持 global probabilistic occupancy/search：高 posterior 区形成 components，规划跨 components 的路线，再周期性更新；局部 bearing 交会可由 Reynaud/本题集合层补足。
- [B-inference][Q4] 可迁移的是 belief update 与“negative evidence 必须尊重生成机制”的逻辑，不是 transient likelihood。一次 no-signal 既不应硬判源不存在，也不应无条件删除位置。

## 11. What does NOT transfer

- [Paper] transmitter omnidirectional，directionality 在 robot receive antenna；[B-inference] 不能声称 Song 直接解决 directional emitter。
- [Paper] RSS 与校准 antenna pattern 是 likelihood；[B-inference] B 题量测为停点 bearing / no-signal，且固定地点误差不随机，需重建 likelihood。
- [Paper] 连续监听 transient packets；[B-inference] B 题一次检测固定 5 s、只能监听一个频道，时间和 channel scheduling 完全不同。
- [Paper] (k_{max}) periods 无新源只是 heuristic stop；[B-inference] 不满足 B 题“确保所有干扰源被清除”的确定性要求。

## 12. Concrete modelling implications

- [B-inference] 对 Q3 推荐 `hard feasible region + probability overlay`：hard layer 保证 $\pm1^\circ$ 真值不被删；belief layer 用 simulator-calibrated error density 和 existence probability 排序动作。
- [B-inference] 对 Q4 令 $s_c=(x_c,y_c,\phi_c,R_c,\tau_c)$。positive/no-signal likelihood 同时考虑距离、覆盖角与 type；为防高维爆炸，优先 particles 或 factorized representation，而不是完整 5-D dense SPOG。
- [B-inference] Song 的主要价值是全局多源 belief/search 与 no-signal 语义警告；定位到某一频道后，局部 next waypoint 更适合用 hard-set / Dehghan 风格滚动评分。
