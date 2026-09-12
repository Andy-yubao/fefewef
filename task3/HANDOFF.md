# Q3 当前交接

最后更新：2026-09-12（Asia/Shanghai）

## 当前采用模型

唯一当前策略为：

`candidate_041_dynamic_open_route_deferred_cross_view`

开始论文写作或继续实验前，按顺序阅读：

1. `task3/facts/README.md`
2. `task3/facts/current_model.md`
3. `task3/facts/performance.md`
4. `task3/facts/history.md`

旧 `task3/report/`、`strategy_design*.md` 和 README 后半部分均为历史研究材料，不得用其中 Geometry、020 或 038 的“当前策略”表述覆盖上述结论。

## 当前状态

- Candidate 041 已确定采用；
- Candidate 042 密集首段/Z 字方案已否决并从代码中撤销；
- 当前完整回归：112 项通过；
- 最终随机验证：30 场、399/399 个源清除，合并 274.62 s/源；
- 固定 16 源 5 场：041 均值 4001.87 s；
- 不宣称全局最优或统计显著优于所有历史策略。

## 复核命令

```powershell
D:\tools\anaconda3\envs\onn\python.exe -m pytest task3/test -q

D:\tools\anaconda3\envs\onn\python.exe -m task3.experiments.run_offline `
  --cases 20 --seed 20261016 --workers 1 `
  --policies candidate_041_dynamic_open_route_deferred_cross_view `
  --output task3/results/raw/optimization/reproduce_candidate041_random20.jsonl.gz
```

仓库可能包含队友未提交的改动。编辑前检查 Git 状态；不得修改、移动或删除 `prompt/`。
