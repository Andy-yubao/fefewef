# Dehghan et al. 2014 全文精读

## 元数据与证据边界

- [Paper] Seyyed M. Mehdi Dehghan, Seyyed A. Asghar Shahidian, Hadi Moradi, *Optimal path planning for DRSSI based localization of an RF source by multiple UAVs*, **2014 Second RSI/ISM International Conference on Robotics and Mechatronics (ICRoM)**, pp. 558-563, DOI `10.1109/ICRoM.2014.6990961`。所读为 6 页完整会议论文；作者显示顺序以论文首页为准，数据库规范名交叉核验。
- [Paper] 页码以下同时给 PDF 页和会议页。本文只处理一个 RF source、三架 UAV、DRSSI/EKF；对 B 题可迁移的是滚动 waypoint 结构，不是测量方程。

## 1. Paper problem

- [Paper] 三架带 RSSI 传感器的 UAV 在 NLOS 条件下定位一个发射功率未知、可随时间变化的静态 RF source；每个时刻联合形成 DRSSI，EKF 更新位置，再选择下一组 waypoint（Sec. I, PDF p.1 / p.558）。
- [Paper] 文中提到实际任务可依次定位多个源，但所建模型和仿真只是一组 UAV 定位一个 unique target；多源扩展列为 future work（Sec. V-A 与 Conclusion, PDF pp.3,6 / pp.560,563）。

## 2. Measurement model

- [Paper] dB 域 RSSI 为发射功率减路径损耗：(P_r=P_t-PL)，路径损耗为
  \[
  PL=PL_{d_0}+10\lambda\log(d/d_0),
  \]
  见 Eqs. (1)-(2)（Sec. II, PDF p.2 / p.559）。
- [Paper] 以 UAV 1 为 reference receiver，构成 (N-1) 个独立形式的 DRSSI：
  \[
  \Delta P_{r,i,j}^k=P_{r,j}^k-P_{r,i}^k
  =-10\lambda\log\frac{\|P-U_j^k\|}{\|P-U_i^k\|},
  \]
  因而消去未知发射功率（Eqs. (4)-(5), PDF p.2 / p.559）。

## 3. Noise / uncertainty

- [Paper] 单个 RSSI 受零均值 white Gaussian noise，方差 $\sigma^2$；DRSSI 方差为 $2\sigma^2$，共享 reference sensor 的差分噪声相关，$R_d$ 非对角（Eqs. (3), (6), (13), PDF pp.2-3 / pp.559-560）。
- [Paper] 仿真把 shadowing 标准差设为 7 dB（Sec. VI, PDF p.5 / p.562）。

## 4. State / feasible-set / belief representation

- [Paper] UAV 位置 $U_i^k=[x_i^k,y_i^k]^T$ 已知；状态只含静态源位置 $s_k=[x_p^k,y_p^k]^T$，转移矩阵为单位阵（Eqs. (7)-(8), Secs. III-IV, PDF pp.2-3 / pp.559-560）。
- [Paper] 非线性 DRSSI observation Eq. (9) 在当前估计处以 Jacobian Eqs. (10)-(12) 线性化，交由 EKF 迭代更新；表示是 point estimate + covariance，不是 hard feasible set。

## 5. Objective

- [Paper] 当前/候选 waypoint 的 FIM 为
  \[
  I(\hat P)=J^TR_d^{-1}J,
  \]
  见 Eq. (17)（Sec. V-B, PDF p.4 / p.561）。
- [Paper] 对每组候选下一方向最大化 (\det I(\hat P))，等价于缩小局部 CRLB uncertainty ellipse area；文中有时写矩阵范数符号，但正文明确称 determinant（Eqs. (20)-(21), PDF p.4 / p.561）。

## 6. Main theorem / proposition / closed-form

- [Paper] 没有闭式全局最优定理或 convergence proof。作者称选择结果为 sub-optimal path，并警告初始化不佳会陷入局部极值；收敛证明列为 future work（Sec. V-B, Conclusion, PDF pp.4,6 / pp.561,563）。

## 7. Algorithm

- [Paper] 每个 UAV 以恒速 (v) 在采样间隔 (T) 内走固定步长：
  \[
  U_i^{k+1}=U_i^k+S_i^k,\quad
  S_i^k=vT[\cos\theta_i^k,\sin\theta_i^k]^T,
  \]
  同时受最大转角、UAV 间距及相对目标估计的距离约束（Eqs. (14)-(16), PDF pp.3-4 / pp.560-561）。
- [Paper] 枚举/组合各 UAV 可选 steering angles，计算每一组 next waypoints 的局部 FIM determinant，选最大者，移动、采样 DRSSI、EKF 更新，再重复（Sec. V-B, Eqs. (19)-(21), PDF p.4 / p.561）。初始信息不足以算 FIM 时先朝当前 target estimate 移动。

## 8. Complexity

- [Paper] 论文未报告 Big-O、候选方向数或 wall-clock time。
- [B-inference] 若每架 UAV 有 $q$ 个离散方向，原三 UAV 联合枚举可达 $q^3$ 组；单机器狗缩减为 $q$ 个候选评分。若原文实际用连续非线性优化，则复杂度取决于求解器和初值，本文没有足够信息量化。

## 9. Validation

- [Paper] 三 UAV、半径 5 km 的圆形搜索区、150 km/h、每 5 s 测量；初始源估计为圆心且 covariance 覆盖搜索区（Sec. VI, PDF p.5 / p.562）。
- [Paper] 初始 UAV 坐标为 ([1,1]^T,[2,0]^T,[1,-1]^T) km。比较 CRLB path 与“直接飞向当前估计”的 bio-inspired path；1000 次 Monte Carlo 中终点位置 RMSE 为 0.23 km 对 1.12 km（Fig. 2, Table 1, PDF pp.5-6 / pp.562-563）。
- [Paper] 未报告总 path length、完成时间、运行时间或统计置信区间；不能把 RMSE 攝改善解释为总任务时间更短。

## 10. What transfers to CUMCM B（Q1-Q4）

### Transferable

- [B-inference][Q3] `candidate waypoint -> score -> choose -> move -> measure -> update -> replan` 是可直接借用的 receding one-step architecture。
- [B-inference][Q2/Q3] 候选几何不能只“朝估计点直走”；需保留改善交会角度的动作，否则可能形成共线坏几何。
- [B-inference][Q3] 用当前 estimate/belief 对候选的 predicted information 评分，再由实际观测更新，是实现局部定位模块的清晰接口。

## 11. What does NOT transfer

### Non-transferable

- [Paper] DRSSI/path-loss likelihood、7 dB Gaussian shadowing、共享 reference sensor 的 $R_d$、RSSI Jacobian 和 EKF observation update 均绑定 RSSI；[B-inference] B 题只有 bearing hard bound，不可照搬。
- [Paper] 三架 UAV 必须同步取差分信号；[B-inference] B 题是一只机器狗，不能在同一时刻产生空间差分 RSSI。
- [Paper] 单源且无搜索、频道、光学确认与清除；[B-inference] 它不支持 Q3 的未知源数终止保证。

## 12. Concrete modelling implications

### B题单机器狗 sequential loop

| 元素 | B题改写 |
|---|---|
| state | 当前机器人位置/频道；每频道 existence 状态、hard feasible region、可选 belief、已清除标记 |
| action | 移动到候选点 (s')，选择频道 (c)，执行检测/光学/清除 |
| observation | `bearing ±1°`、`no signal`、`≤5 m strong signal`、光学/清除结果 |
| state update | bearing 扇区求交；probabilistic likelihood 更新；保守处理 no-signal；清除后冻结该频道 |
| candidate generation | coverage/search 网格、belief ridge/高质量点、鲁棒近正交交会点、20 m 接近点 |
| score | 预期或最坏不确定性下降 / 总动作时间；时间为 (\|s'-s\|/5 + 1_{c\ne c_0}\cdot1 + 5 + 1_{opt}\cdot3 + 1_{clear}\cdot2) s |
| termination | 所有频道完成有保证的搜索覆盖，所有已发现源均光学确认并清除；不能只用 posterior threshold |

- [B-inference] Dehghan 应作为局部 next-waypoint implementation architecture；不应作为 global multi-source search model 或 bearing likelihood 文献。
