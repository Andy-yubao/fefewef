# Q1 当前模型：有界示向一致集合与精确圆域裁剪

设第 (i) 个检测站为 (S_i)，读数为 \hat\theta_i)，误差界为 \(\varepsilon=1^\circ\)。令 (u(\theta)=(\cos\theta,\sin\theta))。目标点 (X) 满足该读数当且仅当

\[
u(\hat\theta_i-\varepsilon)\times(X-S_i)\ge0,\qquad
u(\hat\theta_i+\varepsilon)\times(X-S_i)\le0.
\]

因此单站约束是前向角扇区的两个闭半平面；所有观测的可行集为 (P=\cap_i W_i)。实现通过边界线两两求交、可行性筛选和凸包得到有界凸多边形；如果约束未形成有界集则显式报错。

最终区域为 (\Omega=P\cap B(0,1800)\)。若 (P) 顶点均在圆内，凸性保证圆域不生效；否则对线段和圆弧作解析裁剪，而不以正多边形近似圆。

区域直径为 (D=\max_{x,y\in\Omega}\|x-y\|)。纯多边形时枚举顶点对；含圆弧时还检查端点的反向圆周点和两弧的对径点，覆盖圆弧内部极值。所有容差集中在 `GeometryTolerance`。
