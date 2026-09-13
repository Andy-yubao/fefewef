#set page(
  paper: "a4",
  margin: (
    top: 2.45cm,
    bottom: 2.35cm,
    left: 3cm,
    right: 3cm,
  ),
  numbering: "1",
  number-align: center + bottom,
)

#set text(
  lang: "zh",
  font: ("Times New Roman", "SimSun"),
  size: 10.5pt,
  fill: black,
)

#set par(
  justify: true,
  first-line-indent: (amount: 2em, all: true),
  leading: 0.78em,
  spacing: 0.78em,
)

#set figure(gap: 0.45em)

#show figure: set block(
  above: 0.35em,
  below: 0.45em,
  breakable: false,
)

#show figure.caption: set text(
  font: "SimSun",
  size: 9pt,
)

#set math.equation(numbering: "(1)")


// -------------------- 标题格式 --------------------

#let major(title) = block(
  width: 100%,
  above: 1.35em,
  below: 1em,
  breakable: false,
)[
  #align(center)[
    #text(
      font: "SimHei",
      size: 14pt,
      weight: "bold",
    )[#title]
  ]
]

#let sec(title) = block(
  above: 1.15em,
  below: 0.72em,
  breakable: false,
)[
  #text(
    font: "SimHei",
    size: 12pt,
    weight: "bold",
  )[#title]
]

#let subsec(title) = block(
  above: 0.95em,
  below: 0.58em,
  breakable: false,
)[
  #text(
    font: "SimHei",
    size: 10.5pt,
    weight: "bold",
  )[#title]
]

#let algorithm(title, body) = block(
  width: 100%,
  above: 0.90em,
  below: 0.95em,
)[
  #line(length: 100%, stroke: 0.8pt)
  #v(0.30em)

  #set par(
    first-line-indent: 0em,
    leading: 0.65em,
    spacing: 0.42em,
  )

  #text(size: 9.5pt, weight: "bold")[#title]

  #v(0.25em)
  #line(length: 100%, stroke: 0.45pt)
  #v(0.35em)

  #text(size: 9.5pt)[#body]

  #v(0.30em)
  #line(length: 100%, stroke: 0.8pt)
]

#let table-title(body) = block(
  above: 0.80em,
  below: 0.38em,
)[
  #align(center)[
    #text(size: 9.5pt)[#body]
  ]
]


// ==================================================
// 问题二
// ==================================================

#major[六、问题二： 第二检测点选择及定位区域优化]


#sec[6.1 第一次示向约束与定位区域]

已知第一次检测点 $S_1$ 及测得的示向度 $theta_1$。由于示向度与真实方位角之间的误差不超过 $plus.minus 1 degree$，第一次检测后不能确定干扰源的唯一位置，只能得到其可能位置范围。

设目标圆域为 $Omega$，干扰源位置为 $G$。首先定义两个方位角 $alpha$ 和 $beta$ 的最小角度差为

$ delta(alpha, beta)
  = min(
      abs(alpha - beta),
      360 degree - abs(alpha - beta)
    ).
$ <eq-angle-diff>

其中，$delta(alpha,beta)$ 的取值范围为 $[0 degree,180 degree]$。例如，$359 degree$ 与 $1 degree$ 的角度差为 $2 degree$。

设 $beta(S,g)$ 表示从检测点 $S$ 指向位置 $g$ 的方位角。在检测点 $S$ 测得示向度 $theta$ 后，与该观测相符的位置集合为

$ W(S, theta)
  = {
      g :
      5 < norm(g - S) <= 1500,
      delta(beta(S, g), theta) <= 1 degree
    }.
$ <eq-w>

式 @eq-w 中，距离下界 5 m 是由于距离干扰源不超过 5 m 时无法获得示向度；距离上界 1500 m 为题目给出的最大有效接收半径。

由于干扰源还必须位于半径为 1800 m 的目标圆域 $Omega$ 内，因此第一次检测后的定位区域为

$ F_1 = Omega inter W(S_1, theta_1).
$ <eq-f1>

后续第二检测点的选择均以 $F_1$ 为依据。按照问题一的定义，区域 $A$ 的直径为

$ D(A)
  = max_(p, q in A) norm(p - q).
$ <eq-diameter>

$D(A)$ 越小，表示干扰源的位置范围越小。

#figure(
  image(
    "q2_geometry_candidate_regions.pdf",
    width: 76%,
  ),
  caption: [第一次定位区域与第二检测点候选区域],
)


#sec[6.2 第二检测点候选区域]

第二次检测点应与第一次定位区域保持适当距离。由于干扰源的最大有效接收半径为 1500 m，若检测点到 $F_1$ 中任意位置的距离均超过 1500 m，则第二次检测一定无法接收到信号。

因此，第二检测点的理论候选区域定义为

$ C_f
  = {
      s :
      min_(g in F_1) norm(s - g) <= 1500
    }.
$ <eq-cf>

考虑机器狗仍在目标圆域内选取检测点，实际搜索区域取为

$ C = Omega inter C_f.
$ <eq-candidate>

还可以定义保证接收到信号的区域

$ C_g
  = {
      s :
      max_(g in F_1) norm(s - g) <= 1000
    }.
$ <eq-cg>

这是因为所有干扰源的有效接收半径均不小于 1000 m。若 $s in C_g$，则无论干扰源实际位于 $F_1$ 中何处，第二次检测都可以收到信号。

但 $C_g$ 的范围通常较小，可能排除交会角较好的检测点。因此，实际选点仍在区域 $C$ 内进行，$C_g$ 只用于说明能够保证接收信号的位置范围。


#sec[6.3 第二次检测后的定位区域的更新]

设第二检测点为 $s$。第二次检测可能出现三种情况：正常获得示向度、未检测到信号以及距离干扰源不超过 5 m。

若正常获得第二次示向度 $theta_2$，则干扰源同时满足两次检测条件，因此新的定位区域为

$ F_2
  = F_1 inter W(s, theta_2).
$ <eq-f2-bearing>

若未检测到信号，由于干扰源的实际有效接收半径未知，不能直接排除距离 $s$ 小于 1500 m 的全部位置。但是题目保证所有干扰源的有效接收半径均不小于 1000 m，因此可以确定

$ norm(G - s) > 1000. $

于是新的定位区域为

$ F_2
  = F_1 without B(s, 1000),
$ <eq-f2-nosignal>

其中 $B(s,1000)$ 表示以 $s$ 为圆心、1000 m 为半径的圆盘。

若检测点与干扰源距离不超过 5 m，则可直接采用光学探测仪进行精确定位。此时可认为干扰源位置已经确定，定位区域直径为

$ D(F_2) = 0.
$ <eq-f2-near>

因此，第二次检测后的定位区域可写为

$ F_2 = cases(
    F_1 inter W(s, theta_2)
      & "获得示向度",
    F_1 without B(s, 1000)
      & "未检测到信号",
    {G}
      & "距离不超过 5 m",
  ).
$ <eq-update>


#sec[6.4 第二检测点选择方法]

第二检测点的目标是使第二次检测后的定位区域尽可能小。因此，本文直接以第二次定位区域的直径作为评价指标。

由于干扰源在 $F_1$ 中的具体位置未知，在 $F_1$ 内按面积均匀选取 $N_G$ 个可能位置。对于每个可能位置，再考虑有效接收半径及第二次示向误差的不同取值，计算在候选检测点 $s$ 进行第二次检测后得到的定位区域。

定义候选点 $s$ 的评价函数为

$ J(s)
  = E(D(F_2) | F_1, s).
$ <eq-objective>

若将第二次检测的三种结果分别记为 $o_1$、$o_2$ 和 $o_3$，则式 @eq-objective 可写为

$ J(s)
  = sum_(i=1)^3
      P(o_i | s) D(F_2^(o_i)).
$ <eq-objective-expand>

其中，$P(o_i|s)$ 表示在候选点 $s$ 得到第 $i$ 种检测结果的概率，$D(F_2^(o_i))$ 为对应的定位区域直径。

因此，第二检测点选择为

$ s^*
  = arg min_(s in C) J(s).
$ <eq-opt>

计算时采用逐级网格搜索。首先以 250 m 的网格间距搜索整个候选区域，再在较优位置附近分别采用 100 m 和 50 m 的网格进行细化。正式计算使用 80 个可能目标位置和 5 个示向误差节点。

#algorithm[
  算法 1　第二检测点选择
][
  输入：第一次检测点 $S_1$、示向度 $theta_1$、候选区域 $C$、目标位置数 $N_G$ 和误差节点数 $N_e$。\

  Step 1：根据式 @eq-w 和式 @eq-f1 构造第一次定位区域 $F_1$；\

  Step 2：在 $F_1$ 内选取可能的干扰源位置，并在区域 $C$ 内生成第二检测点候选点；\

  Step 3：对每个候选点计算第二次检测的各种可能结果，并按式 @eq-update 求得 $F_2$；\

  Step 4：计算各定位区域的直径及其期望值 $J(s)$；\

  Step 5：按照 250→100→50 m 的顺序逐级细化，取 $J(s)$ 最小的点作为第二检测点。
]

#figure(
  image(
    "selected_points_comparison.pdf",
    width: 73%,
  ),
  caption: [不同第二检测点对应的期望定位区域直径],
)


#sec[6.5 不同选点方法的比较]

为比较不同第二检测点选择方法，设置期望直径法、几何选点法、平均 GDOP 法、FIM E-最优法和随机选点法五种方法。

期望直径法按照式 @eq-objective 选择第二检测点；几何选点法主要考虑两次示向线的交会角；平均 GDOP 法按照几何精度因子选点；FIM E-最优法按照 Fisher 信息矩阵的最小特征值选点；随机选点法则在相同候选区域内随机选择检测点。

除第二检测点的选择方法外，五种方法均使用相同的第一次检测结果、测试场景、示向误差和定位区域计算方法。实验生成 400 个基础状态，每个状态进行 25 次第二次检测，共得到 10000 个测试场景，随机种子为 20260911。

主要比较第二次检测后的定位区域直径，结果如表 6-1 所示。

#table-title[
  表 6-1　五种第二检测点选择方法的定位区域直径（m）
]

#table(
  columns: (1.65fr, 1fr, 1fr, 1fr, 1fr, 1fr),
  align: center,
  stroke: 0.35pt,

  [方法],
  [均值],
  [中位数],
  [P90],
  [P95],
  [最大值],

  [平均 GDOP],
  [52.38],
  [47.54],
  [71.66],
  [81.12],
  [306.71],

  [期望直径],
  [53.32],
  [47.64],
  [68.63],
  [78.73],
  [341.17],

  [几何选点],
  [67.67],
  [56.27],
  [120.21],
  [142.46],
  [453.83],

  [FIM E-最优],
  [193.41],
  [66.42],
  [609.44],
  [817.15],
  [1352.20],

  [随机选点],
  [588.04],
  [278.29],
  [1495.00],
  [1495.00],
  [1495.00],
)


#sec[6.6 数值结果分析]

由表 6-1 可见，期望直径法的定位区域直径均值为 53.32 m，中位数为 47.64 m。几何选点法、FIM E-最优法和随机选点法的均值分别为 67.67 m、193.41 m 和 588.04 m，均大于期望直径法。

期望直径法的 P90 和 P95 分别为 68.63 m 和 78.73 m，在五种方法中均为最小。这说明对于定位区域较大的测试情况，期望直径法能够较好地控制第二次检测后的定位范围。

平均 GDOP 法的平均定位区域直径为 52.38 m，略小于期望直径法的 53.32 m；两种方法的中位数分别为 47.54 m 和 47.64 m，也十分接近。

若以平均 GDOP 法减去期望直径法的定位区域直径计算配对差，其均值约为 $-0.95$ m，95% 的聚类 bootstrap 区间为

$ [-2.26, 0.13] " m". $

该区间包含 0，因此现有实验结果不能说明两种方法在平均定位区域直径上存在明显差异。

平均 GDOP 法的选点计算时间约为期望直径法的五分之一。因此，若更重视 P90、P95 等较差情况下的定位效果，可采用期望直径法；若对选点计算速度要求较高，可采用平均 GDOP 法。

#figure(
  image(
    "diameter_cdf_updated.pdf",
    width: 82%,
  ),
  caption: [五种第二检测点选择方法的定位区域直径经验分布],
)


#sec[6.7 结论]

第一次检测后，可根据示向度的 $plus.minus 1 degree$ 误差范围和目标圆域确定干扰源的定位区域 $F_1$。第二检测点在区域 $C$ 内选择，并以第二次检测后定位区域直径的期望值作为选点依据。

实验结果表明，期望直径法的 P90 和 P95 最小；平均 GDOP 法的平均定位区域直径与其接近，但计算速度更快。因此，一般情况下采用期望直径法选择第二检测点，在计算时间要求较高时可采用平均 GDOP 法。
