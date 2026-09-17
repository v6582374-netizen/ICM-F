# Mu 语义迁移指南（taskfirst_mu_v1）

## 变更摘要

- 任务层成为一等公民: `mu_task = c - s`。
- 职业层仅做派生汇总: `mu_occ = beta - alpha = sum_j w_ij * mu_task_ij`。
- 禁止裸字段 `mu`（任何下游读取 `mu` 的逻辑必须改为 `mu_task` 或 `mu_occ`）。

## 数据产物变更

### `data/processed/task_dna_{soc}_authoritative_sc.csv`

- 新增列: `mu_task`。
- 明确列: `dims`, `sim`, `sources`（与 `evidence_note` 保持一致）。
- 规则: `mu_task` 必须严格等于 `c - s`。

### `data/processed/task_dna_{soc}_authoritative_agg.json`

- `mu` 重命名为 `mu_occ`。
- 新增: `schema_version=taskfirst_mu_v1`。
- 新增: `mu_definition_occ`, `mu_definition_task`。
- 新增: `consistency_check`（双路径一致性校验）。
- 新增: `weighted_hist_mu_task`（按权重汇总的 `mu_task` 分布）。

## 下游脚本迁移

- 预测/仿真脚本必须读取 `authoritative_sc.csv` 中的 `mu_task`。
- 若确需职业层汇总，请读取 `authoritative_agg.json` 中的 `mu_occ`（仅用于摘要/校验）。

## 运行顺序

1. 先执行 `occupational_dna/relabel_task_dna_authoritative_sc.py` 生成含 `mu_task` 的权威任务层 CSV。
2. 再执行 `occupational_dna/aggregate_authoritative_sc.py` 生成含 `mu_occ` 的聚合 JSON。
3. 使用 `data/processed/mu_refactor_audit_report.md` 检查是否仍有裸 `mu` 产物残留。

## 兼容性提示

不再生成裸 `mu` 字段。如需兼容旧脚本，请显式映射为 `mu_occ` 并标注弃用。
