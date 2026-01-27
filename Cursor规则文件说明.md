# MCM/ICM 竞赛规则体系

基于《正确写作美国大学生数学建模竞赛论文》一书的指导原则，本项目构建了一套完整的 Cursor 规则体系，将专家经验代码化，使其能够实时纠正写作过程中的偏差。

## 📋 目录

- [项目概述](#项目概述)
- [规则体系结构](#规则体系结构)
- [核心规则说明](#核心规则说明)
- [使用指南](#使用指南)
- [规则文件详解](#规则文件详解)

## 🎯 项目概述

本规则体系旨在将《正确写作美国大学生数学建模竞赛论文》一书中的定性建议转化为 Cursor 可执行的 `.mdc` 规则。这不仅是将书籍数字化，而是将"专家经验"代码化，使其能够实时纠正写作过程中的偏差。

### 核心特性

- ✅ **实时写作指导**：Agent 会在写作过程中实时纠正偏差
- ✅ **结构化强制**：假设部分必须包含理由，摘要必须包含特定要素
- ✅ **自动化编译**：使用 latexmk 进行自动化编译和错误处理
- ✅ **一致性校验**：可验证代码实现与论文描述的一致性
- ✅ **专业排版**：数学公式、图表、引用格式的标准化

## 📁 规则体系结构

```
.cursor/
├── rules/
│   ├── core-identity.mdc          # Agent专家角色定义（始终应用）
│   ├── core-mcm-voice.mdc         # 语调、人称、时态规范（始终应用）
│   ├── latex/
│   │   ├── build-toolchain.mdc    # latexmk编译与调试指南（始终应用）
│   │   ├── math-syntax.mdc        # 数学公式排版规范
│   │   ├── mcm-assumptions.mdc    # 假设与理由的结构化强制
│   │   └── mcm-structure.mdc      # 论文目录结构与章节要求
│   ├── workflows/
│   │   ├── mcm-abstract.mdc       # 摘要写作专项指导
│   │   └── consistency-check.mdc  # 代码与论文一致性检查
│   └── python/
│       └── visualization.mdc      # 图表生成规范
└── .cursorignore                  # 排除构建产物和临时文件
```

## 🔧 核心规则说明

### 1. 核心语调与人称规范 (`core-mcm-voice.mdc`)

**始终应用**：适用于所有 `.tex` 和 `.md` 文件

#### 人称使用
- **强制**：使用第一人称复数（"We"）指代作者
- **禁止**：不得使用 "I"、"You" 或 "The authors"（除非引用）

#### 语态偏好
- **优先**：使用主动语态，更直接有力
  - ❌ 错误："The equation was solved using the Newton-Raphson method."
  - ✅ 正确："We solved the equation using the Newton-Raphson method."
- **例外**：当行为者未知或不相关时使用被动语态

#### 时态一致性
- **现在时**：描述模型、既定事实和永久真理
- **过去时**：描述建模过程中已执行的程序
- **将来时**：仅在"未来工作"部分使用

#### 词汇约束
- 避免描述基本的代数操作
- 使用精确术语：
  - "problem" → "challenge", "obstacle", "issue", "discrepancy"
  - "get" → "obtain", "derive", "acquire"

### 2. 假设与理由的结构化强制 (`latex/mcm-assumptions.mdc`)

**适用场景**：生成或编辑"假设"部分时

#### 结构要求
必须使用 `itemize` 环境，每个假设必须包含理由：

```latex
\item \textbf{假设名称}. \textit{Justification:} 解释文本。
```

#### 内容指南
1. **相关性**：假设必须简化问题或填补数据空白
2. **理由**：必须基于物理、常识或数据限制，避免循环推理
3. **变量**：如果假设引入常数，立即定义其符号和值

#### 示例
```latex
\begin{itemize}
    \item \textbf{均匀分布}. \textit{Justification:} 数据显示无显著空间聚类，且缺乏详细地理信息。
    \item \textbf{忽略空气阻力}. \textit{Justification:} 对于所考虑的速度范围（0-10 m/s），空气阻力对总力的贡献小于2%，已通过初步计算验证。
\end{itemize}
```

### 3. 摘要写作的黄金法则 (`workflows/mcm-abstract.mdc`)

**适用场景**：编写 `abstract.tex` 或 `summary.tex` 时

#### 结构检查清单
1. **问题重述**：用自己的话简要重述问题（不要复制提示）
2. **方法**：明确说明使用的建模技术
3. **结果**：必须包含具体数值结果和关键结论（禁止模糊表述）
4. **敏感性**：提及验证或敏感性分析

#### 风格约束
- **无数学符号**：除非绝对必要，避免在摘要中使用复杂数学符号
- **开篇吸引**：第一句必须引人入胜且与现实世界相关
- **长度限制**：严格限制在一页内

#### 对比示例
- ❌ **弱**："We built a model to solve the problem and found good results."
- ✅ **强**："We developed a multi-objective optimization model based on Genetic Algorithms. Our simulation indicates that the optimal strategy reduces costs by 15.4% while maintaining service levels above 98%."

### 4. LaTeX 工程化与自动化编译 (`latex/build-toolchain.mdc`)

**始终应用**：适用于所有 `.tex` 文件

#### 编译命令
使用 `latexmk` 进行编译，不要手动多次运行 `pdflatex`：

```bash
# 编译
latexmk -pdf -interaction=nonstopmode -synctex=1 -outdir=build main.tex

# 清理
latexmk -c
```

#### 错误处理协议
1. **读取日志**：不要依赖终端摘要，读取 `build/` 目录中的 `.log` 文件
2. **识别错误**：搜索 `!`、`Error:` 或 `Undefined control sequence`
3. **修复策略**：
   - 缺少包：在 `main.tex` 前导中添加 `\usepackage{...}`
   - 未定义引用：检查 `references.bib` 键并确保调用 `\bibliography`
   - 数学错误：检查未闭合的括号或数学模式中的无效命令
4. **重试**：再次运行编译命令

#### 包白名单
确保为 MCM 论文加载以下标准包：
- `geometry`（页边距）
- `amsmath`, `amssymb`（数学）
- `graphicx`（图像）
- `booktabs`（专业表格）
- `mcmthesis`（如果可用，使用此类）

### 5. 数学公式排版的语义约束 (`latex/math-syntax.mdc`)

**适用场景**：编写包含数学公式的 LaTeX 文件时

#### 环境选择
- **显示数学**：使用 `\[...\]` 表示未编号方程
- **编号方程**：仅对文本中引用的方程使用 `\begin{equation}...\end{equation}`
- **多行**：使用 `\begin{align}` 进行推导，避免 `eqnarray`（有间距问题）

#### 符号约定
- **变量**：标量为斜体 ($x$)，向量为粗体小写 ($\mathbf{v}$)，矩阵为粗体大写 ($\mathbf{A}$)
- **运算符**：使用 `\sin`, `\cos`, `\log`, `\max`, `\min`，不要写 `log(x)`（会渲染为变量）
- **数学中的文本**：使用 `\text{}` 表示描述性文本

#### 标点符号
- 数学方程是句子的组成部分
- 如果句子需要，必须在数学环境内使用适当的标点（句号或逗号）

### 6. 代码与文档的一致性校验 (`workflows/consistency-check.mdc`)

**适用场景**：当要求"审核模型"或"检查一致性"时

#### 验证流程
1. **提取公式**：在 `sections/model.tex` 中识别数学公式
2. **定位代码**：在 `code/` 中找到对应函数
3. **验证**：
   - 变量名是否匹配？（例如，文本中的 $\alpha$ 在代码中是否命名为 `alpha`？）
   - 逻辑是否相同？（例如，检查循环边界、常数）
   - 单位是否一致？
4. **报告**：提供详细的不一致列表，**未经明确许可不得自动修复**（因为"真相来源"可能不明确）

### 7. 自动化图表生成与插入 (`python/visualization.mdc`)

**适用场景**：生成科学图表时

#### 样式要求
- **背景**：白色背景
- **颜色**：高对比度颜色（色盲友好）
- **字体**：适合打印的大字体
- **格式**：保存为 PDF（.pdf）以获得矢量质量

#### 内容要求
- 每个轴**必须**有标签和单位
- 每个图表**必须**有标题（或在 LaTeX 标题中处理）

#### LaTeX 输出
生成绘图代码时，同时生成 LaTeX 片段：

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\textwidth]{images/filename.pdf}
\caption{详细描述趋势的含义。}
\label{fig:filename}
\end{figure}
```

### 8. 论文结构指南 (`latex/mcm-structure.mdc`)

**适用场景**：规划或检查论文结构时

#### 必需章节（按顺序）
1. **摘要页（Abstract）**：独立的一页摘要
2. **引言**：问题重述、目标和方法概述
3. **假设和理由**：所有假设及其明确理由
4. **模型开发**：数学公式、推导和模型结构
5. **模型求解**：数值方法、算法和求解程序
6. **结果与分析**：关键发现、可视化和解释
7. **敏感性分析**：参数敏感性和模型稳健性
8. **优缺点**：对模型局限性的诚实评估
9. **结论**：贡献和发现的总结
10. **参考文献**：正确格式的引用
11. **附录**（可选）：代码片段、附加数据、详细推导

## 📖 使用指南

### 激活规则

规则文件已配置为自动应用：

- **始终应用**（`alwaysApply: true`）：
  - `core-identity.mdc`
  - `core-mcm-voice.mdc`
  - `build-toolchain.mdc`

- **按需应用**（`alwaysApply: false`）：
  - 其他规则文件根据文件类型和上下文自动触发

### 使用示例

#### 1. 编写假设部分
当您开始编写假设部分时，Agent 会自动提示您为每个假设添加理由。

#### 2. 编写摘要
当您编辑 `abstract.tex` 时，Agent 会检查是否包含所有必需要素（问题重述、方法、结果、敏感性分析）。

#### 3. 编译 LaTeX
当您要求编译文档时，Agent 会使用 `latexmk` 并自动处理错误。

#### 4. 检查一致性
当您要求"检查模型一致性"时，Agent 会验证代码实现与论文描述是否匹配。

## 🔍 规则文件详解

### 核心规则

| 文件 | 描述 | 应用范围 |
|------|------|----------|
| `core-identity.mdc` | 定义 Agent 为 MCM/ICM 学术编辑专家 | 所有 `.tex`, `.md` |
| `core-mcm-voice.mdc` | 语调、人称、时态规范 | 所有 `.tex`, `.md` |

### LaTeX 规则

| 文件 | 描述 | 应用范围 |
|------|------|----------|
| `build-toolchain.mdc` | LaTeX 编译工作流 | 所有 `.tex`, `Makefile`, `latexmkrc` |
| `math-syntax.mdc` | 数学公式排版标准 | 所有 `.tex` |
| `mcm-assumptions.mdc` | 假设部分结构化要求 | 所有 `.tex` |
| `mcm-structure.mdc` | 论文章节结构要求 | 所有 `.tex` |

### 工作流规则

| 文件 | 描述 | 应用范围 |
|------|------|----------|
| `mcm-abstract.mdc` | 摘要写作指南 | `abstract.tex`, `summary.tex` |
| `consistency-check.mdc` | 代码与论文一致性验证 | `.tex`, `.py`, `.m` |

### Python 规则

| 文件 | 描述 | 应用范围 |
|------|------|----------|
| `visualization.mdc` | 科学图表生成标准 | 所有 `.py` |

## 🚀 开始使用

1. **确保虚拟环境已激活**：
   ```bash
   source .venv/bin/activate
   ```

2. **开始编写论文**：
   - 创建 `main.tex` 文件
   - Agent 会自动应用相关规则

3. **使用 Agent 辅助**：
   - 编写时，Agent 会实时提供建议
   - 编译时，Agent 会自动处理错误
   - 检查时，Agent 会验证一致性

## 📚 参考资源

- 《正确写作美国大学生数学建模竞赛论文》
- [MCM/ICM 官方网站](https://www.comap.com/undergraduate/contests/)
- [LaTeX 文档](https://www.latex-project.org/)

## 📝 注意事项

1. **规则优先级**：始终应用的规则会覆盖按需应用的规则
2. **文件匹配**：规则通过 `globs` 模式匹配文件，确保文件命名符合规范
3. **手动覆盖**：如果 Agent 的建议不符合您的意图，可以明确说明您的偏好

## 🤝 贡献

如果您发现规则需要改进或有新的建议，欢迎：
1. 修改相应的 `.mdc` 文件
2. 添加新的规则文件
3. 更新本文档

---

**祝您在 MCM/ICM 竞赛中取得优异成绩！** 🏆
