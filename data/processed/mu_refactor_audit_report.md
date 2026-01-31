# Mu 语义重构审计报告

- 审计日期: 2026-01-31
- 范围: 全仓库搜索 `\bmu\b` 与 `mu_`
- 目标: 禁止裸字段 `mu`，仅允许 `mu_task` 与 `mu_occ`

## 发现摘要

- 代码层面已更新为 `mu_task`/`mu_occ` 语义，聚合脚本强制要求 `mu_task` 列并输出一致性检查。
- LaTeX 文稿中出现的 `\mu` 仅作为数学符号描述，不属于数据字段引用。
- 现有历史产物中仍存在 `mu` 字段（需重新运行聚合脚本以生成 `mu_occ`）。

## 文件清单（需关注的裸 `mu`）

- `data_dictionary.md`（字段说明已迁移为 `mu_occ`/`mu_task`）
- `data/processed/task_dna_15-1252_authoritative_agg.json`（旧产物，需再生成）
- `data/processed/task_dna_17-2199.08_authoritative_agg.json`（旧产物，需再生成）
- `data/processed/task_dna_49-1011.00_authoritative_agg.json`（旧产物，需再生成）
- `data/processed/task_dna_27-3092.00_authoritative_agg.json`（旧产物，需再生成）

## 结论

当前代码与数据字典已完成 `mu_task`/`mu_occ` 语义重构。请对上述历史产物执行聚合脚本以生成带 `schema_version=taskfirst_mu_v1` 的新版本。
