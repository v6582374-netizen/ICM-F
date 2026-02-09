---
name: latex-modular-structure
description: 强制LaTeX项目的模块化结构与main.tex职责边界。用于新增或修改章节内容时。
---

# LaTeX Modular Structure Enforcement

## Quick Start

正文只写在 `sections/*.tex` 中，`main.tex` 仅保留导言区与章节引用。

## Instructions

- `main.tex` 仅包含导言区与 `\include`/`\input` 结构
- 章节内容必须放在 `sections/` 下独立文件
- 新章节先创建文件，再在 `main.tex` 引入
- 禁止将正文合并回 `main.tex`

## Additional Resources

- 原始规则全文见 `reference.md`
