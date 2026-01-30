# LaTeX 引文解析与参考文献章节问题

**问题发现时间**：2026-01-30  
**问题严重程度**：高（影响论文规范性和可读性）

---

## 问题现象

### 1. 引文显示为问号
在编译后的 PDF 中，所有 `\cite{}` 命令解析错误，显示为 `[?]`，例如：
```
from O*NET task data [?] and publicly available AI exposure rubrics [?]
```

### 2. 文献引用章节缺失
论文末尾没有生成 "References" 章节，即使 `references.bib` 文件存在且包含正确的 BibTeX 条目。

### 3. 数据来源章节缺失
前文缺少独立的 "Data Sources" 章节，导致：
- 数据说明被嵌套在模型章节内部，层级混乱
- 读者无法快速定位数据来源信息
- 不符合 MCM/ICM 论文结构规范

### 4. PDF 文件版本混淆
根目录的 `main.pdf` 和 `build/main.pdf` 内容不一致，导致误读旧版本的编译结果。

---

## 根本原因分析

### 原因 1：缺少 BibTeX 支持包
**问题**：`main.tex` 导言区缺少 `natbib` 或类似的参考文献管理包。

**后果**：
- `\cite{}` 命令无法正确解析
- `\bibliography{}` 命令无法生成参考文献列表
- BibTeX 编译步骤无法与主文档正确交互

### 原因 2：缺少独立的数据来源章节
**问题**：项目结构中没有独立的 "Data Sources" 章节。

**后果**：
- `sections/data_description.tex` 被嵌套在 `sections/model_construction.tex` 中通过 `\input` 引入
- 导致数据说明变成了模型章节的 `\subsubsection`，层级过深
- 不符合学术论文"数据-模型-结果"的标准结构

### 原因 3：章节嵌套结构错误
**问题**：`sections/model_construction.tex` 中直接使用了 `\input{sections/data_description}`。

**后果**：
- 造成循环依赖和层级混乱
- 数据说明的层级标题（`\subsubsection`）在正文中不可见或难以导航

### 原因 4：编译输出目录混淆
**问题**：编译命令使用 `-outdir=build`，但用户一直查看根目录的 `main.pdf`。

**后果**：
- 根目录 `main.pdf` 是历史遗留版本，未自动更新
- 实际最新的编译结果在 `build/main.pdf`
- 导致用户误以为修改无效

---

## 解决方案

### 步骤 1：添加 BibTeX 支持包
**修改文件**：`main.tex`

**操作**：在导言区添加以下包：
```latex
\usepackage[numbers]{natbib}  % 参考文献管理，使用数字编号风格
\usepackage{hyperref}         % 可点击的超链接和引用
```

**位置**：在 `\usepackage{amsthm}` 之后添加。

**同时修改参考文献样式**：
```latex
% 原来：
\bibliographystyle{plain}

% 修改为：
\bibliographystyle{plainnat}  % 与 natbib 兼容的样式
\bibliography{references}
```

### 步骤 2：创建独立的数据来源章节
**修改文件**：`main.tex`

**操作**：在模型章节之前插入独立的 Data Sources 章节：
```latex
% --- 第三章：数据来源 ---
\section{Data Sources}
\input{sections/data_description}

% --- 第四章：模型设计 ---
\section{Model Construction and Implementation}
\input{sections/model_construction}
```

**说明**：
- 将 `sections/data_description.tex` 提升为独立章节
- 章节编号顺序自动更新（原第三章变为第四章，以此类推）

### 步骤 3：调整数据说明文件的层级
**修改文件**：`sections/data_description.tex`

**操作**：将最顶层标题从 `\subsubsection` 改为 `\subsection`：
```latex
% 原来：
% \subsubsection{Data Description and Task DNA Source}

% 修改为：
\subsection{Data Description and Task DNA Source}
```

**说明**：
- 因为现在 `data_description.tex` 直接被 `\section{Data Sources}` 引入
- 其内部的顶层标题应为 `\subsection`，而非 `\subsubsection`

### 步骤 4：移除模型章节中的重复引入
**修改文件**：`sections/model_construction.tex`

**操作**：删除以下行：
```latex
\input{sections/data_description}  % ← 删除此行
```

**位置**：在 `\paragraph{Parameter Construction Logic}` 之前。

**同时添加引用说明**：
```latex
% 原来：
We adopt the \textbf{O*NET} occupational database maintained by the U.S. Department of Labor as a unified data source.

% 修改为：
We adopt the \textbf{O*NET} occupational database maintained by the U.S. Department of Labor as a unified data source, with detailed data provenance summarized in Section 3.
```

### 步骤 5：清理正文中的手动编号引用
**修改文件**：`main.tex`

**操作**：删除所有形如 `[23]`、`[3, 24]`、`[14, 22]` 的手动引用占位符，替换为实际的 `\cite{}` 命令或直接删除。

**示例**：
```latex
% 原来：
Cite existing research to build model credibility.[23]

% 修改为：
Cite existing research to build model credibility.\cite{freyosborne2017}

% 或者删除占位符：
List simplifying assumptions and their scientific justifications.
```

### 步骤 6：完整编译流程
**命令**：
```bash
latexmk -pdf -interaction=nonstopmode -synctex=1 -outdir=build main.tex
```

**说明**：
- `latexmk` 会自动执行 `pdflatex` → `bibtex` → `pdflatex` → `pdflatex` 的完整流程
- `-outdir=build` 将所有中间文件和最终 PDF 输出到 `build/` 目录
- 最终生成的 PDF 位于 `build/main.pdf`

### 步骤 7：理解编译输出位置
**重要说明**：

| 文件路径 | 说明 | 更新方式 |
|---------|------|---------|
| `build/main.pdf` | 编译命令的实际输出，**最新版本** | 每次运行 `latexmk` 自动更新 |
| `main.pdf`（根目录） | 历史遗留文件，**旧版本** | 不会自动更新，需手动复制 |

**建议操作**：
1. **删除根目录的 `main.pdf`**（避免混淆）
2. 或者每次编译后手动复制：
   ```bash
   cp build/main.pdf main.pdf
   ```
3. 或者创建符号链接：
   ```bash
   ln -sf build/main.pdf main.pdf
   ```

---

## 验证步骤

### 1. 检查编译日志
查看编译日志中是否包含以下成功标志：
```
Latexmk: applying rule 'bibtex build/main'...
Running 'bibtex  "main.aux"'
```

### 2. 检查 BibTeX 输出文件
确认 `build/main.bbl` 文件存在且包含参考文献列表。

### 3. 检查 PDF 内容
打开 `build/main.pdf`，确认：
- [ ] 所有 `\cite{}` 命令显示为正常的数字编号（如 `[1]`、`[2]`），而非 `[?]`
- [ ] 目录中包含独立的 "Data Sources" 章节（Section 3）
- [ ] 论文末尾包含 "References" 章节
- [ ] 章节编号连续且正确

### 4. 检查引用一致性
运行以下命令检查所有 `\cite{}` 是否在 `references.bib` 中有对应条目：
```bash
# 提取所有 cite 命令
rg '\\cite\{([^}]+)\}' -o -r '$1' --no-filename | sort -u > cited_keys.txt

# 提取 references.bib 中的所有 key
rg '@\w+\{([^,]+),' references.bib -o -r '$1' --no-filename | sort -u > bib_keys.txt

# 比较差异
comm -23 cited_keys.txt bib_keys.txt  # 显示在正文中引用但 bib 中不存在的 key
```

---

## 预防措施

### 1. 强制执行引用规范
**规则**：在代码中使用数据源时，必须同步完成以下操作：

1. ✅ 在 `references.bib` 中添加 BibTeX 条目
2. ✅ 在 `sections/data_description.tex` 中更新数据表格
3. ✅ 在表格中使用 `\cite{key}` 引用
4. ✅ 验证 key 的一致性

### 2. 禁止手动编号引用
**错误示例**：
```latex
According to World Bank data (2024), ...  % ❌ 无法追踪来源
See reference [23] for details.          % ❌ 手动编号
```

**正确示例**：
```latex
According to the World Bank \cite{worldbank2024gdp}, ...  % ✅ 可追踪
```

### 3. 使用模板检查清单
在提交前运行以下检查：
```bash
# 检查是否有未定义的引用
rg 'Citation.*undefined' build/main.log

# 检查是否有 [?] 标记
rg '\[\?\]' build/main.pdf

# 检查 References 章节是否存在
rg -i 'references|bibliography' build/main.pdf
```

### 4. 版本控制建议
**建议添加到 `.gitignore`**：
```gitignore
# LaTeX 编译产物
build/
*.aux
*.log
*.out
*.toc
*.bbl
*.blg
*.synctex.gz

# 根目录的 PDF（应该用 build/main.pdf）
/main.pdf
```

**原因**：
- 避免提交编译中间文件
- 强制团队成员都查看 `build/main.pdf`
- 减少版本冲突

---

## 相关文档

- [LaTeX Build Pipeline](.cursor/rules/latex/build-toolchain.mdc)
- [数据引用规范](.cursor/rules/python/coder-role.mdc#data_citation_standards)
- [模块化结构规范](.cursor/rules/latex/modular-structure.mdc)

---

## 附录：完整的修改清单

| 文件 | 修改类型 | 具体内容 |
|-----|---------|---------|
| `main.tex` | 添加包 | `\usepackage[numbers]{natbib}` 和 `\usepackage{hyperref}` |
| `main.tex` | 修改样式 | `\bibliographystyle{plainnat}` |
| `main.tex` | 添加章节 | `\section{Data Sources} \input{sections/data_description}` |
| `main.tex` | 清理引用 | 删除所有 `[数字]` 形式的手动引用 |
| `sections/data_description.tex` | 调整层级 | `\subsubsection` → `\subsection` |
| `sections/model_construction.tex` | 移除重复引入 | 删除 `\input{sections/data_description}` |
| `sections/model_construction.tex` | 添加交叉引用 | "summarized in Section 3" |

---

## 总结

本次问题的核心在于：
1. **缺少 BibTeX 支持包**导致引用系统失效
2. **章节结构不合理**导致数据来源信息不可见
3. **编译输出位置混淆**导致误读旧版本文件

通过添加必要的包、重组章节结构、规范引用流程，问题得到根本性解决。

**关键教训**：
- LaTeX 引用系统需要完整的编译流程（pdflatex → bibtex → pdflatex × 2）
- 章节结构必须符合"数据-模型-结果"的学术规范
- 始终检查 `build/` 目录下的最新编译产物，而非根目录的历史文件
