---
name: consistency-check
description: 检查LaTeX模型描述与代码实现的一致性。用于用户要求“审计模型”或“检查一致性”时。
---

# Consistency Check Protocol

## Quick Start

先在 `sections/model.tex` 抽取公式，再在 `code/` 中定位对应实现并逐项对照。

## Instructions

- 对比变量命名、逻辑实现与单位一致性
- 仅报告差异，不自动修复
- 发现歧义时提示源头不明

## Additional Resources

- 原始规则全文见 `reference.md`
