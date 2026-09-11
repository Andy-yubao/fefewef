# Calafiore 2026 全文精读

## 元数据与证据边界

- [Paper] Giuseppe C. Calafiore, *Set-Membership Localization via Range Measurements*, arXiv:2603.04867；所读版本为作者公开的 26 页稿，首页注明已被 *SIAM Journal on Optimization* 接收（PDF p.1）。
- [Paper] 本文只研究已知 anchor 到未知点的 range / squared-range；下述页码指 PDF 页码（与正文页码基本一致）。
- [B-inference] 它为 B 题提供集合估计的规范语言，不提供 bearing-sector、连续移动选点、polygon diameter 或任务规划算法。

## 1. Paper problem

- [Paper] 给定 (m) 个已知 anchor (a_i\in\mathbb R^n)，由含 unknown-but-bounded (UBB) 误差的距离测量估计未知位置 (x\in\mathbb R^n)，目标是返回保证包含所有一致位置的集合，而不是单点估计（Sec. 1, PDF pp.1-4）。
- [Paper] 论文强调这是无需初始点的全局 localization；它可为后续需要初始椭球的递归线性化方法提供初始集（Sec. 1.1, PDF p.4）。

## 2. Measurement model

- [Paper] squared-range 与 plain-range 模型分别为
  \[
  y_i=\|x-a_i\|_2^2+e_i,\qquad
  z_i=\|x-a_i\|_2+e_i,
  \]
  并同时允许 absolute interval error 与 relative interval error（Eqs. (2.1)-(2.2), Sec. 2, PDF p.4）。
- [Paper] 四种组合均被换算为
  \[
  \|x-a_i\|_2^2=\xi_i,\qquad \xi_i\in[\xi_i^-,\xi_i^+],
  \]
  具体端点变换见 Eqs. (2.3)-(2.7)（PDF pp.4-5）。

## 3. Noise / uncertainty

- [Paper] 误差不设概率分布，只要求落在独立区间；作者解释区间可来自物理极限、校准证书、制造商精度或截断统计模型（Remark 1, PDF pp.5-6）。
- [Paper] 每次测量的 exact consistency region 是球壳
  \[
  S_i=\{x:\sqrt{\xi_i^-}\le \|x-a_i\|_2\le\sqrt{\xi_i^+}\},
  \]
  全部测量的 exact feasible set 为
  \[
  \mathcal X_{\rm true}=\bigcap_{i=1}^m S_i,
  \]
  一般非凸（Eq. (2.9), PDF p.5）。

## 4. State / feasible-set representation

- [Paper] 对所有 (p=m(m-1)/2) 对测量方程相减，消去 (\|x\|^2)，得到线性 difference-of-measurements (d.o.m.) 方程（Eq. (3.1), Sec. 3.1, PDF p.7）。
- [Paper] Proposition 3.1 证明 d.o.m. 一致位置构成 polyhedron (\mathcal X_d\)，且 (\mathcal X_{\rm true}\subseteq\mathcal X_d)（PDF p.7）。Proposition 3.3 给出只含线性不等式与一个标量辅助变量的显式表示（Eq. (3.4), PDF pp.8-9）。
- [Paper] 另由每个球壳的上界得到闭球 (H_i=\{x:\|x-a_i\|_2\le\sqrt{\xi_i^+}\})。论文定义
  \[
  \mathcal X=\mathcal X_d\cap\bigcap_i H_i,
  \]
  并称其为 localization set；这是凸的 guaranteed outer bound，而非 exact feasible set（Eqs. (3.6)-(3.7), Sec. 3.3, PDF pp.9-10）。
- [Paper] (\mathcal X_d) 可空或无界；rank 与 LP feasibility 条件见 Remark 3。即便 d.o.m. polyhedron 无界，与闭球交后的 (\mathcal X) 仍可有界（PDF pp.8-10）。

## 5. Objective

- [Paper] 主要计算目标是得到简单的 outer box / outer ellipsoid；它们保证包含 (\mathcal X\)，因而包含 (\mathcal X_{\rm true})（Sec. 5, PDF p.13）。
- [Paper] inner ball 最大化半径；inner ellipsoid 最大化 `trace(W)`（半轴长度之和），不是最小体积外椭球（Problems (4.6), (4.10), PDF pp.12-13）。
- [Paper] outer box 对每个正交方向分别求 (x^Tv) 的最小/最大；outer ellipsoid 的 SDP 最小化 `trace(P)`，作者明确称为 suboptimal minimum-size ellipsoid（Propositions 5.1-5.2, PDF pp.13-16）。

## 6. Main theorem / proposition / closed-form

- [Paper] Proposition 3.1-3.3 建立 `exact nonconvex set -> d.o.m. polyhedron outer bound`；关键保证是集合包含，不是 tightness theorem（PDF pp.7-9）。
- [Paper] 作者明确未给 (\mathcal X_{\rm true}\subseteq\mathcal X) 的正式 tightness bound；数值上 anchor 围绕目标分布较好时更紧，近共线/共面或聚集时更保守（Sec. 3.3, PDF p.10）。
- [Paper] Proposition 5.1 的 outer box 是给定正交轴方向下的精确最小包围区间组合；Proposition 5.2 的 outer ellipsoid 受 S-procedure 充分条件影响，只是次优外椭球（PDF pp.14-16）。

## 7. Algorithm

- [Paper] Sec. 5.3 给出流程：输入 anchors/measurements/bounds；可选解 Eq. (6.6) 检测并最小放宽违界误差；构造 incidence matrix (E)、(w)、projector (Q)；每个轴解两个 SOCP 得 outer box；可选解 SDP (4.10) 得 inner ellipsoid（PDF pp.16-17）。
- [Paper] Sec. 6.1 还用凸二次规划围绕一个中心估计局部搜索 (\mathcal X_{\rm true}) 内点；作者不保证找到全局 feasible point（PDF pp.17-18）。

## 8. Complexity

- [Paper] outer box 的每个 SOCP 有 (n+1) 个变量、(m) 个 SOC 约束和 (2m) 个线性不等式；内点法达到 (\epsilon) 精度的外迭代数为 (O(2\sqrt m\log(1/\epsilon)))，每次迭代约 (O(mn^3+2m^2n^2+8m^3)) flops（Remark 5, PDF pp.14-15）。
- [Paper] outer ellipsoid SDP 含 (q=2^m) 个 ((n+1)\times(n+1)) LMI block 与一个 ((2n+1)\times(2n+1)) block；成本对 (q) 线性而 (q) 对测量数指数增长，(m) 较大时可能不可行（Remark 6, PDF p.16）。

## 9. Validation

- [Paper] Sec. 7 在 (n=2,3)、(m=3\ldots10) 的随机场景中，每种配置做 100 次试验；使用 MATLAB/CVX/Mosek（PDF pp.19-23）。
- [Paper] outer box 平均求解时间在报告硬件上对 (n=2) 低于 1.16 s、对 (n=3) 低于 1.72 s；误差和 box size 随 anchor 数总体下降（Tables 1-6, PDF pp.20-22）。
- [Paper] 另测 10% 概率出现最高 50% relative outlier，并用 Eq. (6.6) 放宽 bounds；作者明确这是偏离原模型假设的“off-label”测试（Table 7, Remark 8 前，PDF pp.22-23）。

## 10. What transfers to CUMCM B（Q1-Q4）

- [B-inference][Q1] 可直接借用术语分层：exact feasible set、convex localization outer set、outer box/ellipsoid。写作时必须说明哪个集合保证含真值，哪个只是计算方便的外逼近。
- [B-inference][Q1] 空交集可被解释为至少一个观测或误差界不一致；Eq. (6.6) 的“最小放宽 bounds”思想可作为数值诊断而非默认篡改题设。
- [B-inference][Q2] 可借用“先保证 containment，再以简单外包络评分候选”的设计原则；例如用第二测点后的 worst-case outer-box width/diameter 评分。

## 11. What does NOT transfer

- [Paper] 全部核心线性化来自 squared-range 方程的 pairwise difference；[B-inference] 方位扇区没有可照搬的 Eq. (3.1) 代数，也没有 d.o.m. polyhedron。
- [Paper] outer ball 只使用 range shell 的半径上界；[B-inference] bearing sector 是半平面楔形，exact feasible set 在目标圆盘裁剪下已是凸集或曲边凸集，不需要本文的 range-specific outer relaxation。
- [Paper] 没有移动传感器、sequential placement、travel cost、bearing model、polygon diameter 或 minimum enclosing circle。因此对 Q2 没有新增核心 sequential-location insight。

## 12. Concrete modelling implications

- [B-inference] P1 文献语言可固定为：角度硬界定义 exact bearing-consistency set；数值实现若用正多边形代替目标圆盘，应显式标为 inner/outer approximation；直径与最小包围圆继续由计算几何自行完成。
- [B-inference] Calafiore 的价值是 formalism/citation support，不是当前瓶颈；P1 literature work can stop。
- [B-inference] 对 Q2 仅保留“保证集 + 外包络评分”的思路，不应把 range-only SOCP/SDP 当作第二检测点策略。
