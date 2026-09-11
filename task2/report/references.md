# 参考文献与适用性说明

1. Hammel, S. E., Hilliard, E. J., Gong, K. F., & Liu, P.-T. (1989).
   Optimal observer motion for localization with bearing measurements.
   *Computers & Mathematics with Applications*, 18(1–3), 171–180.
   https://doi.org/10.1016/0898-1221(89)90134-X
   ——支持“观测运动要权衡交会角、距离和可观测性”；本文没有直接套用其动态模型。

2. Zhao, S., Chen, B. M., & Lee, T. H. (2013). Optimal sensor placement for
   target localisation and tracking in 2D and 3D. *International Journal of
   Control*, 86(10), 1687–1704.
   https://doi.org/10.1080/00207179.2013.792606
   ——支持 bearing-only FIM 传感器布设框架；本文另行处理有限接收与有界误差。

3. Nardone, S. C., & Aidala, V. J. (1981). Observability criteria for
   bearings-only target motion analysis. *IEEE Transactions on Aerospace and
   Electronic Systems*, AES-17(2), 162–166.
   https://doi.org/10.1109/TAES.1981.309141
   ——用于解释共线/近平行几何的不可观或病态性；本题为静态两站交会。

4. Jaulin, L. (2011). Set-membership localization with probabilistic errors.
   *Robotics and Autonomous Systems*, 59(6), 489–495.
   https://doi.org/10.1016/j.robot.2011.03.005
   ——支持有界误差下的集合定位思想；题面给出硬边界，故本文以集合模型为主。

5. Lindley, D. V. (1956). On a measure of the information provided by an
   experiment. *Annals of Mathematical Statistics*, 27(4), 986–1005.
   https://doi.org/10.1214/aoms/1177728069
   ——期望信息增益/贝叶斯实验设计的经典来源。

6. Huan, X., & Marzouk, Y. M. (2013). Simulation-based optimal Bayesian
   experimental design for nonlinear systems. *Journal of Computational
   Physics*, 232, 288–317. https://doi.org/10.1016/j.jcp.2012.08.013
   ——支持用 Monte Carlo 估计非线性观测下 EIG；本文采用离散粒子与结果分箱。

7. Kullback, S., & Leibler, R. A. (1951). On information and sufficiency.
   *Annals of Mathematical Statistics*, 22(1), 79–86.
   https://doi.org/10.1214/aoms/1177729694
   ——EIG 中 KL 信息量的定义来源。

以上文献只用于理论定位和指标解释。题面特有的 1800 m 目标圆、1000–1500 m
接收半径、±1° 硬误差、5 m 近距离事件和 5 m/s 移动速度均直接来自题面，
不是文献结论。

