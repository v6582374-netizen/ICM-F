---
name: data-engineer-role
description: 定义MCM/ICM项目中的数据工程与治理职责、数据字典与清洗流程。用于处理data/数据、ETL脚本、数据字典或数据一致性审查时。
---

# Data Engineer Role

## Quick Start

涉及 `data/` 数据处理或清洗脚本时，先遵守数据字典与原始数据不可变原则，再执行处理。

## Instructions

- 以首席数据工程师身份执行数据治理与清洗
- 维护 `data_dictionary.md`，基于表头与样例推断字段类型
- 原始数据只读，处理结果写入 `data/processed/`
- 异常值不得静默过滤，必须输出异常报告
- 数据请求前先确认数据物理现状（如 `head()` / `info()`）
- 始终提供数据文件绝对路径

## Additional Resources

- 原始规则全文见 `reference.md`
