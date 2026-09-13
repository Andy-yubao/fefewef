# Q2 事实库（论文入口）

更新日期：2026-09-13（Asia/Shanghai）

## 当前四策略

按最新决策，Expected Diameter 已放弃，不作为论文比较、推荐或最终策略。Q2只保留四种第二观测点策略：`gdop_mean`、`geometry`、`fim_e`和`random`。旧报告、原始CSV、图件和代码中关于Expected Diameter的内容只保留为历史实验材料，不能覆盖本事实库。

最终推荐为 **GDOP Mean**：它在统一评测中平均定位直径最低，同时在四个保留策略中具有较低尾部和可接受的选点时间。Geometry为可解释、最快的工程备选；FIM E与Random为对照/反例策略，不推荐作为主方案。

阅读顺序：`current_model.md`、`performance.md`、`history.md`。

## 证据边界

- 固定种子20260911下，400个基础几何状态、每状态25次第二观测，共10,000个有效场景；四策略共享场景、第一次读数、候选域和第二次误差。
- 原始正式批次还包含已放弃的Expected Diameter，故其50,000条记录不能被描述为“四策略最终正式实验”；事实库只引用其中四策略各10,000条的可比子集。
- 评价器对三类观测使用公共保守更新：bearing不读取隐藏接收半径，no-signal只剔除必接收1000m圆盘，near的定位区域直径为零。

## 关键文件

- `task2/results/raw/run_manifest.json`：实验配置和随机种子；
- `task2/results/tables/strategy_summary.csv`：策略汇总；
- `task2/results/tables/pairwise_comparison.csv`：场景聚类bootstrap配对比较；
- `task2/src/`：几何、观测更新与四种保留策略实现；
- `task2/explain.md`：四策略的可复用说明；
- `task2/tests/`：策略、更新语义和数值收敛测试。
