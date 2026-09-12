# Q3 优化执行与成果封存

日期：2026-09-12。用户要求“保留并记录当前最好成果”，本轮停止新增策略与参数搜索。代码、原始动作日志、统计表、图和配置均保留在 task3 下。未执行在线演练、正式提交或 Git 提交。

## 保留结论

**本轮最佳完整验证候选：`candidate_057_posterior_free`，260.80 s/源。** 同一组 30 场中，041 为 287.54 s/源，平均减少 26.74 s/源（9.30%），每场均改善；396/396 个源全部清除。距 220 目标还有 40.80 s/源，需要在当前基础上再降低约 15.64%。不把小样本开发成绩当成已达标证据。

保留 `candidate_049_joint_completion` 为低计算开销备选。原正式基线 041 的默认身份不变，057 标为最佳实验成果，未完成原定大规模晋级验证。本次比较可用于后续继续实验，不能证明官方环境分布上的期望耗时或全局最优。

## 完整配对验证

种子 20261210–20261239，30 场，396 个源；5 m 初始网格。口径为总虚拟时间/总源数，含移动、测量、切频、光学与激光。场景与误差相同，无失败场景剔除。

|候选|s/源|场均虚拟耗时 s|全清场次|相对 041 改善场次|场均程序耗时 s|
|---|---:|---:|---:|---:|---:|
|041 基线|287.54|3795.54|30/30|—|5.81|
|049 完成代价与联合选点|268.20|3540.30|30/30|30/30|7.14|
|053 自由搜索顺序|262.16|3460.51|30/30|29/30|21.79|
|057 后验排序与沿途试清除|**260.80**|**3442.53**|30/30|30/30|24.86|

057 的场景 bootstrap 95% 区间为 [248.18, 274.47] s/源；相对 041 的配对节省区间为 [21.40, 32.59] s/源。057 与 053 的均值差仅 1.36 s/源，不声称两者差异已统计显著。057 最大单场耗时 3905.16 s，053 为 3887.38 s，均值最佳不代表所有尾部指标最佳。程序耗时受机器和并发影响，与比赛虚拟耗时不同。

057 场均移动时间由 2958.61 降至 2646.79 s，测量由 652.67 降至 610.33 s，光学开销由 41.50 增至 47.90 s；主要收益来自移动减少。所有四个候选均无“已有安全证书但清除失败”。有预算的非确定性试清除允许失败，并按真实成本计入。

原先 274.62 s/源对应另一组种子 20261006–20261035（399 源）：049 在相同原场景得到 256.47 s/源、全清。057 未在该组重跑，不将不同批次的均值直接相减。

## 已执行的优化

1. **完整服务代价与联合选点**：预演测量后的可行域变化，以预计完成位置和后续代价选点，并让同一源的多个候选测点参与路径改进。固定 CLEAR 不切换接收频道的计费语义。
2. **安全接收区域与清除区域**：接收判据检查所有保留网格方格角点；清除可在已验证安全区域内选择更近位置。接近证书阈值时局部细化网格，避免全域加密。
3. **搜索与清除融合**：自由安排剩余覆盖点，解除固定角窗口限制；共享停靠测量；清除任务参与整体路线排序。保留有限的最终定位/清除回退。
4. **有预算的试清除**：常规局部试探及沿现有路线零绕路试探，057 沿途总预算 24 次、每源至多 4 次；失败仅按合法光学信息收缩可行域，不伪造清除成功或放宽角度误差。
5. **软后验排序**：将接收半径视为同一源固定的未知量，只积分一次约束区间，给候选排序。均匀位置/接收半径先验是模拟环境下的启发式假设，不参与硬可行域裁剪。
6. **激进分支也已保留**：可移动搜索锚点、冗余覆盖点退休、额外共享扫描、更积极的光学预演及七/八边形覆盖。移动或退休必须检查剩余未知区域全部外包方格仍被覆盖。这些分支只有开发批次证据，不替换 057。

核心实现见 `src/completion_planner.py`、`src/optimized_controller.py`；所有候选通过 `src/policies.py` 显式启用。049、053、057 等均从 041 派生。完成代价预演和路线联合选择是启发式，不是最优性证明；软概率不取代几何安全层。

## 开发实验与可追溯性

043–048 在 10 场开发集上比较，048 为 255.07、同批 041 为 273.73 s/源。049–062 后续使用种子 20261110–20261114 的 5 场开发集；057 在该小批次为 225.43 s/源。最终完整开发统计见 [开发汇总](../results/tables/optimization_final_development/summary.csv)，不同样本数的均值不能直接排名。选择候选使用过的开发数据不作独立验证。

封存前已启动的最后批次均已结束：060 为 225.67、061 为 234.49、062 为 234.29 s/源，各 5 场全清，未超过同批 057 的 225.43。没有因用户停止搜索而遗留后台实验。

30 场验证未用于本轮参数继续调节，但同时比较多个候选，仍有择优偏差；未另加未见过的大规模最终留出集。所有原始批次位于 `results/raw/optimization/optimization_*.jsonl.gz`，保留场景、参数、结果和逐动作记录。后期日志含启动时源码 SHA256；开发早期日志为当时原型记录，不保证最新代码逐动作复现其全部候选。

成果入口：

- [冻结配置、代码哈希与验证状态](../results/tables/optimization_best_snapshot.json)
- [完整验证汇总](../results/tables/optimization_validation/summary.csv)、[配对改善](../results/tables/optimization_validation/paired.csv)、[审计记录](../results/tables/optimization_validation/audit.json)
- [原始参考批次对照](../results/tables/optimization_reference/summary.csv)
- [逐动作复现检查](../results/tables/optimization_replay.json)
- [时间构成图](../results/figures/optimization_057_validation/paired_time_budget.png)、[实际路线图](../results/figures/optimization_057_validation/paired_actual_routes.png)

## 复核方法

以下命令从仓库根目录执行；Python 可替换为团队环境中的等效入口。

```powershell
D:/tools/anaconda3/envs/onn/python.exe -m pytest task3/test -q -p no:cacheprovider
D:/tools/anaconda3/envs/onn/python.exe -m task3.experiments.verify_optimization_replay
D:/tools/anaconda3/envs/onn/python.exe -m task3.experiments.run_offline --cases 30 --seed 20261210 --workers 1 --grid-step 5 --policies candidate_057_posterior_free --output task3/results/raw/optimization/optimization_057_reproduction30.jsonl.gz
D:/tools/anaconda3/envs/onn/python.exe -m task3.experiments.summarize_optimization --inputs task3/results/raw/optimization/optimization_049_validation30.jsonl.gz task3/results/raw/optimization/optimization_053_validation30.jsonl.gz task3/results/raw/optimization/optimization_057_validation30.jsonl.gz --output-dir task3/results/tables/optimization_validation
```

审计程序逐动作重算移动及接口成本，事后对照真实源检查观测误差和清除命中，检查动作唯一编号、成功源集合及配对场景一致性；真实源仅用于模拟器和事后审计，不供规划器读取。测试覆盖边界源、极端角度误差、试探失败回退、覆盖证书、网格细化、频道计费及全清。最终验证状态写入冻结记录。

封存检查结果：**完整测试 138 项通过**；041 历史场景、049 两个验证场景及 057 一个验证场景逐动作回放一致；完整开发及验证日志审计通过；`git diff --check -- task3` 通过。测试不等同于对所有连续场景的性能保证。
