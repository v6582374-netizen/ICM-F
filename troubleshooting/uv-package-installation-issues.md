# UV 包安装问题记录

## 问题概述

在使用 `uv` 工具安装 Python 包（numpy、pandas）和运行 Python 脚本时，遇到了四个连续的问题：
1. 包名拼写错误
2. README.md 文件缺失
3. 包结构配置缺失
4. 运行脚本时使用全局 Python 而非虚拟环境

这些问题涉及项目配置、包结构和 IDE 解释器配置。

---

## 问题 1: 包名拼写错误

### 错误信息
```
× No solution found when resolving dependencies:
  ╰─▶ Because nunpy was not found in the package registry
```

### 原因
输入命令时包名拼写错误：`uv add nunpy` → 应该是 `uv add numpy`

### 解决方案
使用正确的包名：`uv add numpy`

### 经验教训
- 注意包名的拼写，特别是常用库如 `numpy`、`pandas` 等
- 错误信息会明确指出找不到的包名，可以帮助快速定位问题

---

## 问题 2: README.md 文件缺失

### 错误信息
```
OSError: Readme file does not exist: README.md
```

### 原因
在 `pyproject.toml` 中配置了：
```toml
readme = "README.md"
```
但项目根目录下不存在该文件。当 `hatchling` 构建后端尝试验证元数据时，发现 README 文件不存在，导致构建失败。

### 解决方案
**方案选择**：移除了 `readme` 配置项

**原因**：
- 这是学术竞赛项目（MCM/ICM），不需要发布到 PyPI
- 不需要包级别的 README 文档
- 项目已有 `项目结构说明.md` 等文档

**修改内容**：
从 `pyproject.toml` 中删除 `readme = "README.md"` 这一行

### 经验教训
- 如果 `pyproject.toml` 中指定了 `readme`，必须确保文件存在
- 对于非发布项目，可以移除该配置
- 或者创建一个简单的 README.md 文件（即使是空文件也可以）

---

## 问题 3: 包结构配置缺失

### 错误信息
```
ValueError: Unable to determine which files to ship inside the wheel using the following heuristics:
The most likely cause of this is that there is no directory that matches the name of your project (ICM_F or icm_f).
At least one file selection option must be defined in the `tool.hatch.build.targets.wheel` table
```

### 原因
`hatchling` 构建工具在尝试构建包时，会按照以下规则查找包目录：
1. 查找与项目名称匹配的目录（如 `ICM_F` 或 `icm_f`）
2. 查找 `src/` 目录下的包
3. 如果都找不到，就会报错

本项目是学术项目，代码放在 `occupational_dna/` 目录下，并以标准 Python 包形式发布。

### 解决方案
**两步操作**：

1. **创建包结构**：在 `occupational_dna/` 目录下创建 `__init__.py` 文件
   ```python
   # ICM-F project code package
   ```

2. **配置构建工具**：在 `pyproject.toml` 中添加配置
   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["occupational_dna"]
   ```

这样告诉 `hatchling` 将 `occupational_dna` 目录作为包来构建。

### 经验教训
- Python 包必须包含 `__init__.py` 文件才能被识别为包
- 对于非标准项目结构，需要在 `pyproject.toml` 中明确指定包位置
- 学术项目虽然不需要发布，但如果使用 `uv` 等工具管理依赖，仍需要满足基本的包结构要求

---

## 问题 4: ModuleNotFoundError - 运行脚本时使用全局 Python

### 错误信息
```
Traceback (most recent call last):
  File "/Users/shiwen/Downloads/ICM-F/occupational_dna/scheme_a_pipeline.py", line 23, in <module>
    import numpy as np
ModuleNotFoundError: No module named 'numpy'
```

### 原因
使用 Cursor 右上角的运行按钮（▶️）运行 Python 脚本时，默认使用系统全局 Python 解释器（`/opt/homebrew/opt/python@3.14/bin/python3.14`），而不是项目虚拟环境中的 Python。

**根本原因**：
1. Cursor 基于 VSCode，使用 Python 扩展的运行机制
2. 如果没有明确配置，Cursor 会使用系统默认的 Python
3. 使用 `uv add` 安装的包被安装到项目虚拟环境（`.venv`）中，系统全局 Python 无法访问

### 解决方案
**通过 Cursor UI 手动选择 Python 解释器**：

1. **打开命令面板**：
   - 按 `Cmd + Shift + P` (macOS) 或 `Ctrl + Shift + P` (Windows/Linux)
   - 或者点击菜单：`View` → `Command Palette`

2. **选择 Python 解释器**：
   - 输入：`Python: Select Interpreter`
   - 选择该命令

3. **选择项目虚拟环境**：
   - 在弹出的列表中，选择：`./.venv/bin/python (Python 3.14.x)`
   - 或者选择显示为 `./.venv` 的选项

4. **验证**：
   - 查看 Cursor 底部状态栏，应该显示：`Python 3.14.x ('.venv': venv)`
   - 现在运行脚本应该使用虚拟环境中的 Python

**验证方法**：
- 查看状态栏：打开 `.py` 文件后，底部状态栏应显示虚拟环境路径
- 运行测试：运行脚本时不再出现 `ModuleNotFoundError`

### 为什么 Code Runner 和 Cursor 运行按钮行为不同？

1. **Code Runner**：
   - 是第三方扩展
   - 可以独立配置执行器路径
   - 可能已经配置为使用虚拟环境

2. **Cursor 运行按钮**：
   - 使用 VSCode 内置的 Python 运行机制
   - 依赖 Python 扩展选择的解释器
   - 需要明确配置才能使用虚拟环境

### 经验教训
- **虚拟环境隔离**：Python 虚拟环境中的包不会自动被系统 Python 访问
- **IDE 配置重要性**：使用 IDE 运行代码时，必须确保 IDE 选择了正确的 Python 解释器
- **一劳永逸的解决方案**：通过命令面板选择解释器后，Cursor 会记住这个选择（保存在工作区配置中）
- **验证习惯**：运行脚本前，检查状态栏显示的 Python 路径，确保使用的是虚拟环境

### 替代方案
如果手动选择解释器不起作用，可以：
1. 使用 `uv run python occupational_dna/script.py` 命令运行脚本
2. 手动创建 `.vscode/settings.json` 配置文件（详见 `cursor-python-interpreter-config.md`）

---

## 最终配置

### pyproject.toml 最终状态
```toml
[project]
name = "ICM-F"
version = "0.1.0"
description = ""
requires-python = ">=3.14"
dependencies = [
    "numpy>=2.4.1",
    "pandas>=3.0.0",
]

[project.optional-dependencies]
dev = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["occupational_dna"]

[tool.uv]
dev-dependencies = []
```

### 项目结构
```
ICM-F/
├── occupational_dna/
│   ├── __init__.py          # Python package marker
│   └── scheme_a_pipeline.py
├── data/
├── pyproject.toml           # 已修改：移除 readme，添加包配置
└── ...
```

---

## 相关资源

- [Hatchling 文档 - 默认文件选择](https://hatch.pypa.io/latest/plugins/builder/wheel/#default-file-selection)
- [Hatchling 配置文档](https://hatch.pypa.io/latest/config/build/)
- [UV 工具文档](https://github.com/astral-sh/uv)

---

## 日期
2026-01-27
