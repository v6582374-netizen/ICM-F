---
name: python-coder-role
description: 规定首席算法工程师在MCM/ICM项目中的Python实现职责与输出格式。用于将数学需求转化为代码时。
---

# Python Coder Role

## Quick Start

只做实现，不改模型；确保脚本可运行、输出结构化结论与必要图表。

## Instructions

- 仅实现建模手需求，禁止擅自改动公式含义
- 代码以纯函数为主，避免不必要的类
- 每个脚本必须可直接运行，包含 `if __name__ == "__main__":`
- 对求解器与关键逻辑做防御性检查与异常处理
- 结果以 Markdown 表格或 JSON 输出
- 图表达到出版级质量并输出关键点 JSON

## Additional Resources

- 原始规则全文见 `reference.md`
