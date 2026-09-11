// problem1_refined.typ
// 风格目标：参考 2022 B030 / B035 / B086 的国赛论文排版。
// 单文件可编译；无外部图片、无彩色框、无现代卡片式装饰。

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
  first-line-indent: 2em,
  leading: 0.82em,
  spacing: 0.42em,
)

#set figure(
  gap: 0.28em,
)

#show figure: it => block(
  above: 0.35em,
  below: 0.45em,
  breakable: false,
)[
  #it
]

#show figure.caption: set text(
  font: "SimSun",
  size: 9pt,
)

#set math.equation(numbering: "(1)")

// -------------------- 参考论文式层次 --------------------

#let major(title) = block(
  width: 100%,
  above: 1.0em,
  below: 0.80em,
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
  above: 0.75em,
  below: 0.42em,
  breakable: false,
)[
  #text(
    font: "SimHei",
    size: 12pt,
    weight: "bold",
  )[#title]
]

#let subsec(title) = block(
  above: 0.62em,
  below: 0.32em,
  breakable: false,
)[
  #text(
    font: "SimHei",
    size: 10.5pt,
    weight: "bold",
  )[#title]
]

#let small-title(title) = block(
  above: 0.35em,
  below: 0.15em,
  breakable: false,
)[
  #text(weight: "bold")[#title]
]

// 仿早年论文的“算法表”：黑白、上下横线，无填充、无圆角。
#let algorithm(title, body) = block(
  width: 100%,
  above: 0.55em,
  below: 0.65em,
)[
  #line(length: 100%, stroke: 0.8pt)
  #v(0.18em)
  #set par(first-line-indent: 0em, leading: 0.42em, spacing: 0.22em)
  #text(size: 9.5pt, weight: "bold")[#title]
  #v(0.14em)
  #line(length: 100%, stroke: 0.45pt)
  #v(0.24em)
  #text(size: 9.5pt)[#body]
  #v(0.18em)
  #line(length: 100%, stroke: 0.8pt)
]

// 三线表标题，保持与 B035 一类论文相近的朴素风格。
#let table-title(body) = block(
  above: 0.45em,
  below: 0.20em,
)[
  #align(center)[#text(size: 9.5pt)[#body]]
]

#major[五、模型的建立与求解]

#sec[5.1 问题一：多点交会定位区域直径及圆覆盖判别]

本问将示向度的 $plus.minus 1^"°"$ 误差视为确定性边界，先由多检测点约束求得干扰源定位区域 $Omega$，再计算其直径 $D$，最后检验直径为 $D$ 的圆能否覆盖 $Omega$。计算过程依次包括示向约束构造、交会区域求解和覆盖性判别。

#subsec[5.1.1 示向约束与定位区域]

#small-title[(1) 单检测点示向约束]

设第 $i$ 个检测点为 $S_i=(x_i,y_i)$，其测得示向度为 $hat(theta)_i$，待定位干扰源的位置记为 $X=(x,y)$。定义方向单位向量

$
u(theta) = (cos theta, sin theta).
$ <eq-direction>

由题意，真实方位角 $theta_i$ 满足

$
hat(theta)_i-epsilon <= theta_i <= hat(theta)_i+epsilon,
quad epsilon=1^"°".
$ <eq-angle-range>

记两条误差边界方向分别为

$
theta_i^- = hat(theta)_i-epsilon,
quad
theta_i^+ = hat(theta)_i+epsilon.
$ <eq-boundary-angle>

为避免示向度在 $0^"°"$ 与 $360^"°"$ 附近产生额外的分段讨论，采用二维向量叉积描述候选点位于边界射线哪一侧。对二维向量 $a=(a_x,a_y)$、$b=(b_x,b_y)$，定义

$
a times b = a_x b_y-a_y b_x.
$ <eq-cross>

则候选位置 $X$ 与第 $i$ 次观测相容，当且仅当

$
u(theta_i^-) times (X-S_i) >= 0,
$ <eq-halfplane-1>

$
u(theta_i^+) times (X-S_i) <= 0.
$ <eq-halfplane-2>

式 @eq-halfplane-1 和式 @eq-halfplane-2 分别给出两个闭半平面，其公共部分即检测点 $S_i$ 对应的可行方向区域 $W_i$。这样，每次带有示向误差的角度观测都被转化为两个线性几何约束，便于后续统一求交。

#figure(
  image("figures/fig1_single_bearing_wedge.pdf", width: 66%),
  caption: [单检测点示向误差的几何约束（角度示意，非按比例）],
) <fig-single-wedge>

#small-title[(2) 多检测点约束求交]

设共有 $m$ 个检测点。由于真实干扰源位置必须同时满足全部示向约束，因此由测向信息得到的交会区域为

$
P = W_1 inter W_2 inter dots.c inter W_m.
$ <eq-intersection>

每个 $W_i$ 均为凸集，所以 $P$ 仍为凸集。当现有检测点的几何构型能够形成有界且非退化的公共区域时，$P$ 为凸多边形。

令半平面总数为 $h=2m$。本文枚举任意两条半平面边界直线的交点，并将所得交点依次代入全部半平面不等式；仅保留满足所有约束的可行交点，再对这些点按逆时针方向求凸包，即得到交会区域 $P$ 的有序顶点。该方法最坏时间复杂度为 $O(h^3)$。由于问题一涉及的检测点数量较少，该方法计算量较小，同时便于逐点核验。

若交集为空，则说明给定观测之间存在矛盾；若只能形成无界区域，则说明当前检测点提供的独立方向信息不足，需要增加检测点后再进行有限定位区域的计算。

#figure(
  image("figures/fig2_multi_station_intersection.pdf", width: 92%),
  caption: [多检测点示向约束交会与定位区域局部放大],
) <fig-multi-intersection>

#small-title[(3) 目标圆域约束]

题目已知干扰源位于以原点 $O$ 为圆心、半径 $R_0=1800 " m"$ 的目标圆域内。因此，最终定位区域为

$
Omega = P inter B(O,R_0).
$ <eq-omega>

首先检验凸多边形 $P$ 的各顶点。若所有顶点均满足

$
norm(V_j) <= R_0,
$ <eq-inside-disk>

则有 $P subset.eq B(O,R_0)$，此时圆域约束不改变定位区域，即 $Omega=P$。

若存在越出目标圆域的顶点，则需进一步计算多边形边与圆周的交点，并保留圆内有效线段；同时按照圆周极角顺序判断相邻交点之间的圆弧是否满足全部半平面约束。由此可将 $partial Omega$ 精确表示为若干直线段与圆弧的组合，避免将圆周离散为正多边形所带来的近似误差。

#figure(
  image("figures/fig3_active_target_disk_clipping.pdf", width: 76%),
  caption: [目标圆域约束活跃时的解析裁剪],
) <fig-disk-clipping>

#subsec[5.1.2 定位区域直径的求解]

完成交会与圆域裁剪后，$Omega$ 是闭、有界凸集，其边界或者为纯多边形，或者由线段与圆弧共同组成。定位区域直径定义为区域内任意两点欧氏距离的最大值，即

$
D = max_(X,Y in Omega) norm(X-Y).
$ <eq-diameter>

由于距离函数的最大值必在凸集边界上取得，直径求解可直接利用上一节得到的边界表示，并按目标圆域是否参与边界分为连续的两步处理。

#small-title[(1) 目标圆域不活跃：顶点对枚举]

若 $P subset.eq B(O,R_0)$，则 $Omega=P$ 为凸多边形。设其有序顶点为 $V_1,V_2,dots.c,V_n$。固定其中一个端点时，距离函数在凸多边形上的最大值可由顶点取得，故两个直径端点均可从顶点集中选取：

$
D = max_(1 <= j < k <= n) norm(V_j-V_k).
$ <eq-vertex-diameter>

因此，直接枚举 $n(n-1)/2$ 个顶点对即可同步得到直径 $D$ 与一组直径端点 $A,B$，时间复杂度为 $O(n^2)$。该结果同时作为下一步覆盖判别的输入。

#small-title[(2) 目标圆域活跃：边界候选扩充]

若 $P$ 越出目标圆域，则 $partial Omega$ 同时含有线段和圆弧。此时式 @eq-vertex-diameter 的顶点枚举仍保留，但不足以覆盖圆弧内部的驻点，故在原候选集上依次补充以下三类点对：

① 全部线段端点与圆弧端点之间的点对；

② 对任一边界端点 $Q$，若其关于原点的对径点 $-R_0Q/norm(Q)$ 落在有效圆弧上，则将该点加入候选；

③ 若两段有效圆弧中存在极角相差 $pi$ 的一对点，则将该对径点对加入候选。

上述补充与纯多边形情形具有同一逻辑起点：先收集全部边界端点，再补足只可能出现在圆弧内部的对径驻点。对于线段，距离平方关于线段参数为凸函数，最大值只能在线段端点取得；对于圆弧，固定另一点后，内部极值只能出现在反向对径方向。因此三类候选依次覆盖“线段—线段”“线段—圆弧”和“圆弧—圆弧”，最终仍归结为有限点对的距离比较。

#algorithm("算法 1　定位区域直径计算", [
  *输入：* 检测点坐标 $S_i$，示向度 $hat(theta)_i$，误差上界 $epsilon=1^"°"$，目标圆域半径 $R_0=1800 " m"$。

  *Step 1.* 由式 @eq-halfplane-1、@eq-halfplane-2 将每个示向度转化为两个闭半平面约束。

  *Step 2.* 枚举边界直线交点，并利用全部约束筛选可行点，对可行点求凸包，得到交会区域 $P$。

  *Step 3.* 计算 $Omega=P inter B(O,R_0)$。若 $P$ 全部位于圆域内，则直接取 $Omega=P$；否则解析保留有效线段与有效圆弧。

  *Step 4.* 若 $Omega$ 为纯多边形，则枚举全部顶点对；若含圆弧，则补充端点反向点及圆弧对径点候选。

  *Step 5.* 比较全部候选点对之间的距离，取最大值作为 $D$，并返回一组直径端点 $A,B$。

  *输出：* 最终定位区域 $Omega$、区域直径 $D$ 及对应直径端点 $A,B$。
])

#subsec[5.1.3 直径圆的覆盖性判别]

直径为 $D$ 的圆*不能保证*覆盖整个定位区域。为使该结论不依赖圆心的主观选取，首先证明：一旦该圆需要包含一对直径端点，其圆心便被唯一确定，不能再通过平移改变覆盖结果。

设 $A,B in Omega$ 为一对直径端点，即

$
norm(A-B)=D.
$ <eq-ab-diameter>

若某个直径为 $D$ 的圆能够覆盖整个定位区域，设其圆心为 $C$、半径为 $D/2$，则 $A$、$B$ 必同时位于该圆内。由三角不等式，

$
D
= norm(A-B)
<= norm(A-C)+norm(C-B)
<= frac(D,2)+frac(D,2)
= D.
$ <eq-unique-circle>

式 @eq-unique-circle 首尾相等，因此两个不等式必须同时取等号。于是 $A,C,B$ 三点共线，且

$
norm(A-C)=norm(B-C)=frac(D,2).
$ <eq-center>

因此，若直径为 $D$ 的覆盖圆存在，其圆心只能为线段 $A B$ 的中点，候选圆是唯一的。换言之，只需检验这一唯一的直径圆是否包含定位区域的所有边界点，即可回答题目第二问。

#algorithm("算法 2　直径圆覆盖判别", [
  *输入：* 定位区域边界 $partial Omega$、区域直径 $D$ 及一组直径端点 $A,B$。

  *Step 1.* 令候选圆心 $C_D=(A+B)/2$，半径 $R_D=D/2$。

  *Step 2.* 检验所有线段端点与圆弧端点到 $C_D$ 的距离；对有效圆弧，另检验距离函数的内部驻点。

  *Step 3.* 若最大距离不超过 $R_D$，则直径圆覆盖 $Omega$；否则输出距离最大的边界点作为漏覆证据。

  *输出：* 覆盖判定及最远边界点。
])

#subsec[5.1.4 算例与反例检验]

为检验上述算法及覆盖性结论，选取三组检测点及对应示向度进行计算，输入数据如表 1 所示。

#table-title[表 1　六边形算例的检测点与示向度]

#table(
  columns: (18%, 27%, 27%, 28%),
  align: center,
  inset: (x: 4pt, y: 3pt),
  stroke: none,

  table.hline(stroke: 0.8pt),
  [*检测点*], [$x/"m"$], [$y/"m"$], [*示向度/$"°"$*],
  table.hline(stroke: 0.45pt),

  [$S_1$], [713.63], [1193.59], [235.05529],
  [$S_2$], [-939.50], [362.10], [356.78364],
  [$S_3$], [590.63], [-611.06], [117.85767],

  table.hline(stroke: 0.8pt),
)

按照式 @eq-halfplane-1 至式 @eq-omega 进行求交，得到一个六边形定位区域。该区域全部位于目标圆域内，因此本算例中 $Omega=P$。六个有序顶点见表 2。

#table-title[表 2　交会定位区域的有序顶点]

#table(
  columns: (20%, 40%, 40%),
  align: center,
  inset: (x: 4pt, y: 3pt),
  stroke: none,

  table.hline(stroke: 0.8pt),
  [*顶点*], [$x/"m"$], [$y/"m"$],
  table.hline(stroke: 0.45pt),

  [$V_1$], [78.704085], [317.913679],
  [$V_2$], [96.440589], [285.727879],
  [$V_3$], [102.254593], [285.299256],
  [$V_4$], [121.919084], [314.513835],
  [$V_5$], [118.558048], [321.150947],
  [$V_6$], [82.075102], [322.562913],

  table.hline(stroke: 0.8pt),
)

由式 @eq-vertex-diameter 枚举顶点对，可得一组直径端点为 $A=V_1$、$B=V_4$，区域直径为

$
D = norm(V_1-V_4)=43.348530 " m".
$ <eq-numeric-d>

由式 @eq-center 可知，唯一可能的直径圆圆心和半径分别为

$
C_D = frac(V_1+V_4,2)
= (100.311585,316.213757),
$ <eq-cd>

$
R_D = frac(D,2)
= 21.674265 " m".
$ <eq-rd>

计算其余顶点到 $C_D$ 的距离，有

$
norm(V_2-C_D)=30.730658 " m" > R_D,
$ <eq-v2>

$
norm(V_3-C_D)=30.975501 " m" > R_D.
$ <eq-v3>

因此 $V_2$、$V_3$ 均位于该直径圆之外，说明以定位区域直径为直径的圆不能覆盖该六边形定位区域，其几何关系如图 @fig-counterexample 所示。

#figure(
  image("figures/fig4_hexagon_counterexample.pdf", width: 82%),
  caption: [直径圆不能覆盖定位区域的六边形反例],
) <fig-counterexample>

进一步计算该六边形的最小覆盖圆，得到

$
R_("min")=23.098117 " m",
quad
2R_("min")=46.196234 " m" > D.
$ <eq-mec>

这进一步说明，即使允许重新选择圆心，覆盖该定位区域所需的最小圆直径仍大于区域直径。

作为补充，由平面 Jung 定理，

$
R_("min") <= frac(D,sqrt(3)),
quad
2R_("min") <= frac(2D,sqrt(3)) approx 1.155D.
$ <eq-jung>

该结果表明，仅根据区域直径 $D$，一般只能保证存在直径不超过 $2D/sqrt(3)$ 的覆盖圆，而不能保证存在直径恰为 $D$ 的覆盖圆。本算例给出了题目所问命题的直接反例。

#subsec[5.1.5 问题一结论]

综上，本文首先将每个检测点的 $plus.minus 1^"°"$ 示向误差转化为两个线性半平面约束，通过多检测点约束求交获得凸定位区域，并结合半径 $1800 " m"$ 的目标圆域得到最终定位区域 $Omega$。对于纯多边形边界，枚举顶点对即可计算区域直径；对于含圆弧的边界，还需补充端点反向点及圆弧对径点候选。

对于题目提出的圆覆盖问题，结论为：*以定位区域直径为直径的圆不能保证覆盖整个定位区域。* 六边形算例中，定位区域直径为 $43.348530 " m"$，而其最小覆盖圆直径为 $46.196234 " m"$；同时，由直径端点可唯一确定直径圆圆心，该唯一候选圆仍存在定位区域顶点落在圆外。因此，题目第二问的答案是否定的。
