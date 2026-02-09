---
description: "强制执行美赛LaTeX项目架构、虚拟环境管理及临时文件清理规则"
alwaysApply: false
---
# 美赛建模项目 Agent 执行准则

## 1. 严格的项目目录架构

为了防止项目臃肿，所有生成的文件必须遵循以下金字塔式结构，**禁止将非配置文件直接丢弃在根目录**：

### 目录结构规范

- **`/figures/`**: 存放所有图片文件（`.pdf`, `.png`, `.jpg`）。Agent 在 LaTeX 中引用图片时，必须指向此路径。

- **`/code/`**: 存放所有模型源码（`.py`, `.m`, `.cpp` 等）。Agent 不得将长代码段直接粘贴在 `.tex` 主文件中，应建议使用 `\lstinputlisting` 或 `\include`。

- **`/data/`**: 存放原始数据集、中间处理结果（`.csv`, `.xlsx`, `.json`）。

- **根目录 `.`**: 仅允许存放 `main.tex`, `mcmthesis.cls`, `references.bib` 及必要的环境配置文件。

### 约束

- Agent 在创建新文件前，**必须检查其后缀并自动放入对应文件夹**。
- 如果用户要求创建文件，Agent 必须根据文件类型自动选择正确的目录。
- 禁止在根目录创建临时文件、测试文件或数据文件。

### 示例

**错误做法**：
```bash
# 在根目录创建文件
touch test.py
touch figure1.png
```

**正确做法**：
```bash
# 自动放入对应目录
touch code/test.py
touch figures/figure1.png
```

## 2. 强制使用项目虚拟环境 (Venv)

**严禁使用全局系统命令**（如 `pip3 install`）安装依赖，必须识别并使用项目中现有的虚拟环境。

### 识别环境

- **优先寻找**：项目根目录下的 `.venv` 或由 `uv`、`venv` 生成的 Python 解释器。
- **检查方法**：使用 `which python` 或 `python --version` 确认当前使用的解释器路径。

### 安装指令

若缺少依赖，Agent 必须：

1. **方法一**：激活虚拟环境后安装
   ```bash
   source .venv/bin/activate
   pip install <package>
   ```

2. **方法二**：直接使用虚拟环境中的 Python
   ```bash
   ./.venv/bin/python -m pip install <package>
   ```

3. **方法三**：使用 uv（如果项目使用 uv）
   ```bash
   uv pip install <package>
   ```

### 拒绝全局操作

- 如果 Agent 尝试使用全局 `pip` 被系统拦截，**不得转向其他系统级方案**，必须向用户报告虚拟环境路径冲突。
- 任何 terminal 辅助指令必须**预读 `python --version` 或查看路径**，确保位于虚拟环境中。

### 约束

- 任何 terminal 辅助指令必须预读 `python --version` 或查看路径，确保位于虚拟环境中。
- 在执行 Python 相关命令前，必须验证当前使用的是项目虚拟环境。

### 验证步骤

在执行任何 Python 命令前，Agent 应该：

```bash
# 1. 检查 Python 路径
which python
# 应该显示: /path/to/project/.venv/bin/python

# 2. 验证虚拟环境
python --version
# 应该显示项目虚拟环境的 Python 版本

# 3. 如果不在虚拟环境中，激活它
source .venv/bin/activate
```

## 3. 自动化清理测试冗余

Agent 在解决报错或验证逻辑时生成的临时文件**必须在任务结束前自主删除**。

### 清理范围

包括但不限于：
- `test_*.py` - 测试脚本
- `temp_*.tex` - 临时 LaTeX 文件
- `debug.log` - 调试日志
- `*.aux` (非编译必要时) - LaTeX 辅助文件
- 为了测试某一小段逻辑而创建的临时脚本
- `_temp_*.py`, `scratch_*.py`, `check_*.py` 等临时文件

### 执行时机

- **每一个 Task 完成**（用户确认解决问题）后，Agent 必须主动检查并询问：
  > "是否需要我清理刚才生成的临时测试文件？"
  
- 或在确认不再需要后**直接执行清理**：
  ```bash
  # 清理临时文件
  rm -f test_*.py temp_*.tex debug.log
  # 清理 LaTeX 辅助文件（如果不在 build/ 目录中）
  find . -maxdepth 1 -name "*.aux" -o -name "*.log" -o -name "*.out" | xargs rm -f
  ```

### 约束

- **禁止在项目中留下任何 Agent 产生的"脚手架"文件**。
- 所有临时文件必须在任务完成后清理。
- 如果文件对用户有价值，应该询问用户是否保留，而不是直接删除。

### 清理检查清单

在完成任务后，Agent 应该检查：

1. ✅ 是否有 `test_*.py` 文件？
2. ✅ 是否有 `temp_*.tex` 文件？
3. ✅ 是否有 `debug.log` 或其他日志文件？
4. ✅ 是否有根目录下的临时文件？
5. ✅ 是否有为了测试而创建的临时脚本？

### 例外情况

以下文件**不应自动删除**：
- 用户明确要求保留的文件
- 在 `build/` 目录中的编译产物（由 `.gitignore` 管理）
- 在 `.venv/` 目录中的虚拟环境文件
- 配置文件（如 `pyproject.toml`, `.gitignore` 等）

## 综合执行流程

当 Agent 需要执行任务时，应遵循以下流程：

1. **文件创建前**：
   - 检查文件类型
   - 确定正确的目录（`figures/`, `code/`, `data/`）
   - 在正确位置创建文件

2. **Python 操作前**：
   - 检查当前 Python 环境
   - 如果不在虚拟环境中，激活虚拟环境
   - 使用虚拟环境中的工具执行操作

3. **任务完成后**：
   - 检查是否有临时文件
   - 询问用户或直接清理临时文件
   - 确保项目目录整洁

## 违规示例与纠正

### 示例 1：错误创建文件位置

**违规**：
```bash
# Agent 在根目录创建测试文件
echo "test" > test.py
```

**纠正**：
```bash
# 应该创建在 code/ 目录
echo "test" > code/test.py
```

### 示例 2：使用全局 pip

**违规**：
```bash
pip3 install numpy  # 使用系统全局 pip
```

**纠正**：
```bash
source .venv/bin/activate
pip install numpy
# 或
./.venv/bin/python -m pip install numpy
```

### 示例 3：遗留临时文件

**违规**：
```bash
# Agent 创建了 test_model.py 来测试，但忘记删除
# 项目根目录留下 test_model.py
```

**纠正**：
```bash
# 任务完成后自动清理
rm -f test_model.py
# 或询问用户
# "我创建了 test_model.py 用于测试，现在可以删除吗？"
```

---

**记住**：保持项目整洁、使用虚拟环境、及时清理临时文件，这是专业建模项目的基本要求。
