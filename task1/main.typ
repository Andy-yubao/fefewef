// main_condensed.typ
// 问题一压缩版：理论证明与几何图示优先，适合 3--4 页正文。

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
  first-line-indent:(amount: 2em, all:true),
  leading: 0.78em,
  spacing: 0.78em,
)

#set figure(
  gap: 0.45em,
)

#show figure: it => block(
  above: 0.75em,
  below: 0.85em,
  breakable: false,
)[
  #it
]
#show figure.caption: set text(
  font: "SimSun",
  size: 9pt,
)
#show figure: it => block(
  above: 0.35em,
  below: 0.45em,
  breakable:false,
)[
  #it
]

#set math.equation(numbering: "(1)")

// -------------------- 参考论文式层次 --------------------

#let major(title) = block(
  width: 100%,
  above: 1.35em,
  below: 1.00em,
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

#let small-title(title) = block(
  above: 0.78em,
  below: 0.42em,
  breakable: false,
)[
  #text(weight: "bold")[#title]
]

// 仿早年论文的“算法表”：黑白、上下横线，无填充、无圆角。
#let algorithm(title, body) = block(
  width: 100%,
  above: 0.90em,
  below: 0.95em,
)[
  #line(length: 100%, stroke: 0.8pt)
  #v(0.30em)
  #set par(first-line-indent: 0em, leading: 0.65em, spacing: 0.42em)
  #text(size: 9.5pt, weight: "bold")[#title]
  #v(0.25em)
  #line(length: 100%, stroke: 0.45pt)
  #v(0.35em)
  #text(size: 9.5pt)[#body]
  #v(0.30em)
  #line(length: 100%, stroke: 0.8pt)
]

// 三线表标题，保持与 B035 一类论文相近的朴素风格。
#let table-title(body) = block(
  above: 0.80em,
  below: 0.38em,
)[
  #align(center)[#text(size: 9.5pt)[#body]]
]

#major[五、问题一：多点交会定位区域直径及圆覆盖判别]

#sec[5.1 示向约束与定位区域]

题目给出的示向误差是确定性边界，而非随机噪声。因此本文不以单点估计代表干扰源位置，而将每次观测转化为一个可行方向区域，再通过多检测点约束求交得到定位区域，最后分别计算其直径并判断直径圆是否覆盖。

#v(0.9em)
设检测点为 $S_i=(x_i,y_i)$，干扰源位置为 $X=(x,y)$，示向读数为 $hat(theta)_i$，误差上界为 $epsilon=1^"°"$。记

$
theta_i^- = hat(theta)_i-epsilon,
quad theta_i^+ = hat(theta)_i+epsilon.
$ <eq-angle>

对方向单位向量 $u(theta)=(cos theta,sin theta)$，二维叉积定义为

$
a times b=a_x b_y-a_y b_x.
$ <eq-cross>

则 $X$ 与第 $i$ 次观测相容，当且仅当

$
u(theta_i^-) times (X-S_i) >= 0,
quad
u(theta_i^+) times (X-S_i) <= 0.
$ <eq-halfplanes>

这两个闭半平面的交集记为 $W_i$，几何上即以 $S_i$ 为顶点、由 $theta_i^-$ 与 $theta_i^+$ 确定的扇形约束。需要强调的是，$W_i$ 表示与该次观测相容的全部位置，而不是对干扰源真实位置的单点估计。因此，后续多点交会应对这些集合进行求交，不能简单地将各示向线的交点当作唯一答案。

#figure(
  image("fig1_single_bearing_wedge.pdf", width: 56%),
  caption: [单检测点示向误差形成的扇形约束],
) <fig-single-wedge>

设共有 $m$ 个检测点，则多点交会区域为

$
P=W_1 inter W_2 inter dots.c inter W_m.
$ <eq-intersection>

每个 $W_i$ 是凸集，故 $P$ 仍为凸集。令半平面边界总数为 $h=2m$，枚举任意两条非平行边界直线的交点，并将交点代入全部半平面不等式；保留满足全部约束的点后求凸包，即得到 $P$ 的有序顶点。该过程最坏复杂度为 $O(h^3)$，且每个顶点都有明确的几何来源。图2中的六边形并非人为拟合出的轮廓，而是由有效边界的交会关系自然产生的凸定位区域。

#figure(
  image("fig2_multi_station_intersection.pdf", width: 82%),
  caption: [多检测点示向约束交会形成六边形定位区域],
) <fig-multi-intersection>

题目还给出干扰源位于半径 $R_0=1800\,"m"$ 的目标圆域内，因此最终区域为

$
Omega=P inter B(O,R_0).
$ <eq-omega>

若 $P$ 的全部顶点均位于圆域内，则 $Omega=P$，目标圆域约束没有进一步缩小定位范围；否则计算多边形边与圆周的交点，保留圆内线段及满足半平面约束的圆弧。这样，$partial Omega$ 可统一表示为线段和圆弧的组合，并避免以粗糙正多边形近似圆周造成额外误差。

#figure(
  image("fig3_active_target_disk_clipping.pdf", width: 66%),
  caption: [目标圆域约束活跃时的解析裁剪],
) <fig-disk-clipping>

#sec[5.2 定位区域直径]

定位区域直径定义为

$
D=max_(X,Y in Omega) norm(X-Y).
$ <eq-diameter>

若 $Omega$ 为纯多边形，距离最大值可由顶点对取得，枚举 $n(n-1)/2$ 个顶点对即可得到 $D$。若边界含圆弧，则保留全部端点，并补充圆弧上可能产生最大距离的反向对径点。线段上的距离最大值只能出现在端点，圆弧上的内部极值只能出现在反向对径方向，因此连续边界问题仍可化为有限候选点对比较。

#algorithm("算法 1　定位区域直径计算", [
  *输入：* 检测点 $S_i$、示向度 $hat(theta)_i$、误差上界 $epsilon$、目标圆域半径 $R_0$。\
  *Step 1.* 用式 @eq-halfplanes 将每个示向度转化为两个闭半平面。\
  *Step 2.* 枚举边界交点并筛选可行点，求凸包得到 $P$。\
  *Step 3.* 计算 $Omega=P inter B(O,R_0)$，解析保留有效线段和圆弧。\
  *Step 4.* 枚举边界端点，并对有效圆弧补充反向对径候选。\
  *Step 5.* 比较候选点对距离，输出 $Omega$、直径 $D$ 及一组端点 $A,B$。
])

#sec[5.3 直径圆的覆盖性判别]

区域直径描述区域内最远两点的距离，但不代表以此为直径的圆一定能够覆盖区域。设 $A,B in Omega$ 为一组直径端点，满足

$
norm(A-B)=D.
$ <eq-ab-diameter>

若存在直径为 $D$ 的覆盖圆，设圆心为 $C$、半径为 $D/2$，则由三角不等式

$
D=norm(A-B)
<= norm(A-C)+norm(C-B)
<= frac(D,2)+frac(D,2)=D.
$ <eq-unique-circle>

首尾相等迫使 $A,C,B$ 共线且

$
norm(A-C)=norm(B-C)=frac(D,2),
quad C_D=frac(A+B,2).
$ <eq-center>

因此，若直径圆存在，其圆心只能是直径端点中点，不能通过平移圆心改善覆盖结果。只需检验 $partial Omega$ 上最远点到 $C_D$ 的距离是否超过 $D/2$，即可完成覆盖判别。

这一结论给出了覆盖判别的关键：直径 $D$ 只刻画定位区域内部最远两点之间的距离，而圆覆盖问题还取决于其他边界点相对于直径中点的分布。故“区域直径为 $D$”与“存在直径为 $D$ 的覆盖圆”是两个不同命题，不能由前者直接推出后者。

#sec[5.4 六边形反例与理论说明]

图 @fig-multi-intersection 所示的六条边界线形成一个凸六边形。取其中一对直径端点 $A,B$，由式 @eq-center 唯一确定直径圆圆心 $C_D$ 和半径 $D/2$。图 @fig-counterexample 中另一个边界顶点位于该圆外，故直径为 $D$ 的圆不能覆盖整个定位区域。

#figure(
  image("fig4_hexagon_counterexample.pdf", width: 72%),
  caption: [直径圆不能覆盖六边形定位区域的反例],
) <fig-counterexample>

若允许重新选择圆心，最小覆盖圆半径记为 $R_("min")$。.

平面 Jung 定理给出一般上界

$
R_("min") <= frac(D,sqrt(3)),
quad 2R_("min") <= frac(2D,sqrt(3)) approx 1.155D.
$ <eq-jung>

该定理说明覆盖圆直径可能大于区域直径；本六边形进一步给出具体的严格关系 $2R_("min")>D$。因此，区域直径可以严格计算，但“以区域直径为直径的圆必能覆盖区域”这一命题不成立。

#sec[5.5 结论]

本文将示向误差转化为半平面约束，通过多点求交和目标圆域裁剪构造定位区域；对线段—圆弧混合边界补充反向对径候选后，得到区域直径。进一步证明：一旦直径端点确定，直径圆的圆心即被唯一确定。六边形反例表明，该唯一候选圆仍可能无法覆盖定位区域；Jung 定理则给出最小覆盖圆相对区域直径的一般理论上界。

综上，问题一的最终结论是：*多点示向约束可以严谨地求得定位区域及其直径，但以定位区域直径为直径的圆不能保证覆盖整个定位区域。*
