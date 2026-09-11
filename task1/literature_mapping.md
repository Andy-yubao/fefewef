# Q1 文献映射与证据边界

| 来源 | Paper states | We reuse | B-problem inference | Not supported |
|---|---|---|---|---|
| Isler & Bajcsy (2006) | 有界不确定性观测可表示为平面凸多边形子集；多次观测通过集合求交合并；论文以交集面积衡量不确定性，并研究传感器选择。 | “一次观测给出全部一致位置，多观测取交”的集合语义，以及凸集合表示。 | 将本题 `±1°` bearing 逆像具体写成角扇区及两个半平面，以欧氏直径而非面积评价 Q1。 | 该文没有直接给出本题的角扇区公式、1800 m 圆盘裁剪、最终直径算法或直径圆覆盖结论。 |
| Calafiore (2026) | 对 unknown-but-bounded 距离测量定义与观测及误差界相容的精确集合，并构造有包含保证的凸外估计/包围集。 | guaranteed feasible localization set 与 exact set / outer approximation 的术语纪律。 | 本题 bearing 扇区本身已是凸集，故直接精确求交，无需照搬其距离测量的球壳与外逼近代数。 | 其测量是 range，不是 bearing；不能据此声称本文已经解决 Q1 的半平面交或圆弧直径。 |
| Jung (1901) | 平面 Jung 定理给出：直径为 \(D\) 的有界集合存在半径不超过 \(D/\sqrt3\) 的覆盖圆。 | 将 \(2D/\sqrt3\) 作为仅由区域直径能够得到的一般覆盖上界。 | 因 \(2/\sqrt3>1\)，该普适上界并不等同于“存在直径为 \(D\) 的覆盖圆”；本题另由六边形实例直接检验。 | 定理不能单独推出给定六边形覆盖失败，也不能替代该实例的直径端点唯一性论证和最小覆盖圆计算。 |

## 参考文献

1. V. Isler and R. Bajcsy, “The Sensor Selection Problem for Bounded Uncertainty Sensing Models,” *IEEE Transactions on Automation Science and Engineering*, 3(4):372–381, 2006. DOI: 10.1109/TASE.2006.876615.
2. G. C. Calafiore, “Set-Membership Localization via Range Measurements,” arXiv:2603.04867, 2026; manuscript states acceptance by *SIAM Journal on Optimization*.
3. H. W. E. Jung, “Ueber die kleinste Kugel, die eine räumliche Figur einschliesst,” *Journal für die reine und angewandte Mathematik*, 123:241–257, 1901. DOI: 10.1515/crll.1901.123.241. EuDML: <https://eudml.org/doc/149122>.
