# Yang et al. 2013 全文精读（BLOCKED）

## 元数据与证据边界

- [Paper metadata] Chun Yang, Lance M. Kaplan, Erik Blasch, Michael Bakich, *Optimal Placement of Heterogeneous Sensors for Targets with Gaussian Priors*, **IEEE Transactions on Aerospace and Electronic Systems**, vol. 49, no. 3, pp. 1637-1653, July 2013, DOI `10.1109/TAES.2013.6558009`。作者、卷期页码和 DOI 已由 IEEE landing page、Crossref/OpenAlex 与 DBLP 交叉核实。
- **BLOCKED:** 2013 期刊全文未能从合法公开渠道获得。已检查 IEEE Xplore（浏览器访问两次超时且无开放 PDF）、OpenAlex（closed、无 repository full text）、ResearchGate（request-only）、SciSpace（只提供摘要入口）、DTIC/CiteSeerX。可公开获得的是四位作者 2011 年 Fusion conference/DTIC 前身 *Optimal Placement of Heterogeneous Sensors in Target Tracking*，不是 2013 期刊全文。
- 按任务纪律，本文件不把摘要或 2011 前身冒充期刊正文，不伪造期刊版 section/page/equation。下列 `[Precursor]` 只说明前身可直接支持的结构；期刊版尚未核实的内容标为 `[Unverified]`。

## 1. Paper problem

- [Paper metadata/abstract] 目标是从任意 Gaussian prior 出发，为不同类型、不同质量的 heterogeneous sensors 推导 placement conditions；类型包括 range、bearing-only 及混合，并允许跨多个时步的独立测量。
- [Precursor] 2011 版明确以 target tracking 为背景，将 mobility model (F,Q)、measurement quality (R) 和 geometry (H) 区分，并讨论带移动成本的时空 placement（abstract/Introduction, conference PDF p.1）。

## 2. Measurement model

- [Paper metadata/abstract] bearing-only 被显式覆盖，但 2013 正文的具体量测方程、Jacobian 与编号未核实。
- [Precursor] 前身把 ranging、bearing-only、TOA/TDOA 作为 heterogeneous measurement types；其正文公式不能无核验地归入 2013 期刊版。

## 3. Noise / uncertainty

- [Paper metadata/abstract] initial target location 由 arbitrary Gaussian prior 描述；sensors 可有不同 measurement quality，且测量独立。
- [Unverified] 无全文不能确认正文对所有 bearing measurements 的精确 Gaussian noise、距离依赖或跨时独立条件，也不能给页码/公式号。

## 4. State / feasible-set / belief representation

- [Paper metadata/abstract] 使用 Gaussian prior 与 updated information matrix，而不是 hard feasible set。
- [Precursor] prior information 与新量测信息在 information form 下结合；但 2013 版究竟称 FIM、updated FIM、Bayesian information matrix 还是 posterior information matrix，需全文复核。

## 5. Objective

- [Paper metadata/abstract] 摘要只说 maximization of the information matrix；没有全文时不能判定正文各情形究竟以 determinant、trace、特征值还是 Loewner/matrix ordering 为最终标量目标。
- [Precursor] 2011 版以 updated FIM 的几何优化为中心，但这不足以满足本任务对 2013 scalar criterion 的精确核验。

## 6. Main theorem / proposition / closed-form

- **[Paper] 未核实：期刊全文不可得。** 不记录 theorem 数字或闭式最优条件。

## 7. Algorithm

- [Paper metadata/abstract] 声称给出 placement strategies，并允许 several time steps 的 multiple independent measurements。
- [Unverified] 这并不能证明它是“收到一次实际 observation 后基于 posterior 重选第二点”的 online greedy policy；也可能只是给定 Gaussian prior 的多时步设计。必须在全文获得后复核。

## 8. Complexity

- [Paper] 未报告（全文不可得，不能核实）。

## 9. Validation

- [Paper metadata/abstract] placement performance 以 simulation examples 展示。
- [Unverified] 场景、样本数、基线和数值提升均未核实。

## 10. What transfers to CUMCM B（Q1-Q4）

- [B-inference][Q2] 可暂把 `prior information + candidate sensor information -> updated information criterion` 作为概率路线的文献线索，但在取得期刊全文前不应作为关键公式唯一来源。
- [B-inference][Q2] 第一条 bearing 后可人为建立 bounded-support 分布（uniform、triangular、truncated centre-concentrated 或 simulator empirical），计算候选第二点的 expected performance；这属于 B 题额外建模假设，不是题目事实。

## 11. What does NOT transfer

- [B-inference] 题目事实只有 fixed-location error 不变且全局在 ([-1^\circ,1^\circ]) 内；不能写 `±1° = Gaussian σ`。
- [B-inference] 即使 2013 正文使用 Gaussian likelihood，其普通 CRLB regularity 通常依赖参数无关 support 和可交换微分/积分。uniform/truncated likelihood 若 support 随真实 bearing 平移，端点随参数变化，经典 score 均值为零与标准 CRLB 推导可能失效；需重推、平滑化或改用 Bayesian/Barankin/ZZB 类界。该判断是统计建模推论，不归因给 Yang。
- [B-inference] 没有证据表明论文包含 B 题 travel cost、连续可达域、硬 $\pm1^\circ$ containment guarantee。

## 12. Concrete modelling implications

### Route A - hard-bound robust

- [B-inference] 主模型维护第一观测扇区 $U_1$，对每个可达候选 $s_2$ 优化所有 $x\in U_1$ 与所有 admissible error 下的 worst-case updated diameter/area，并显式加入移动和 5 s 测量时间。

### Route B - probabilistic

- [B-inference] 在 hard support 内另设误差密度，做 expected diameter、expected entropy 或 posterior covariance 评分；必须用仿真校准和敏感性分析区分 uniform、triangular、truncated Gaussian-like 与 empirical distribution。

## Yang vs Zhao：对 B题第二检测点的真正增量

| 问题 | Zhao 2013（Wave 1 已全文核实） | Yang 2013（本轮证据边界） |
|---|---|---|
| target knowledge | coarse point estimate；关键几何分析固定权重/距离 | [abstract] arbitrary Gaussian prior 描述位置不确定性 |
| prior uncertainty | 无集合/prior covariance | [abstract] 有 Gaussian prior；正文进入公式方式未核实 |
| bearing model | 有，FIM 明确 | [abstract] 显式包含 bearing-only；正文公式未核实 |
| sequential placement | tracking control / 几何构造，不是 hard-set 第二点 policy | [abstract] 可跨 several time steps；online observation-conditioned 与否未核实 |
| objective | D-opt / isotropic tight-frame 几何 | [abstract] updated information matrix；具体标量目标 BLOCKED |
| travel cost | 无 | [precursor] 提到移动成本；2013 具体处理 BLOCKED |
| hard ±1° guarantee | 无 | 无已核实保证 |

- [B-inference] 真正可能的增量是“prior covariance 不再压成一个点，并与新传感器信息联合评价”；但由于期刊全文 BLOCKED，本轮不能把它升级为已核实的闭式第二点规则。
