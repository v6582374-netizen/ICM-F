---
name: latex-build-toolchain
description: 规范LaTeX编译、错误定位与包管理流程。用于编译main.tex或排查LaTeX错误时。
---

# LaTeX Build Toolchain

## Quick Start

编译一律使用 `latexmk`，失败时先读 `.log` 再定位错误类型。

## Instructions

- 仅使用 `latexmk` 编译与清理
- 错误排查先读 `.log`，再按错误类型处理
- 缺包加入导言区，引用错误检查 `references.bib` 与引用命令
- 常用包需保持齐全（`geometry`、`amsmath` 等）

## Additional Resources

- 原始规则全文见 `reference.md`
