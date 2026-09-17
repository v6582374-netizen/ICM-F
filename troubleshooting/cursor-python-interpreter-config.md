# Cursor Python 解释器配置指南

## 问题描述

使用 Cursor 右上角的运行按钮（▶️）运行 Python 脚本时，默认使用系统全局 Python，而不是项目虚拟环境中的 Python，导致 `ModuleNotFoundError`。

## 原因分析

1. **Cursor 基于 VSCode**：Cursor 使用 VSCode 的 Python 扩展和运行机制
2. **默认解释器未设置**：如果没有明确配置，Cursor 会使用系统默认的 Python
3. **虚拟环境未被识别**：虽然项目有 `.venv` 目录，但 Cursor 没有自动选择它

## 一劳永逸的解决方案

### 方法 1：通过 Cursor UI 选择解释器（推荐）

**步骤：**

1. **打开命令面板**：
   - 按 `Cmd + Shift + P` (macOS) 或 `Ctrl + Shift + P` (Windows/Linux)
   - 或者点击菜单：`View` → `Command Palette`

2. **选择 Python 解释器**：
   - 输入：`Python: Select Interpreter`
   - 选择该命令

3. **选择项目虚拟环境**：
   - 在弹出的列表中，选择：
     ```
     ./.venv/bin/python (Python 3.14.x)
     ```
   - 或者选择显示为 `./.venv` 的选项

4. **验证**：
   - 查看 Cursor 底部状态栏，应该显示：`Python 3.14.x ('.venv': venv)`
   - 现在运行脚本应该使用虚拟环境中的 Python

**优点**：
- ✅ 图形界面，操作简单
- ✅ Cursor 会记住这个选择（保存在工作区配置中）
- ✅ 适用于所有 Python 文件

### 方法 2：手动创建配置文件

如果方法 1 不起作用，可以手动创建配置文件：

**步骤：**

1. **创建 `.vscode` 目录**（如果不存在）：
   ```bash
   mkdir -p .vscode
   ```

2. **创建 `settings.json` 文件**：
   ```bash
   # 在项目根目录执行
   cat > .vscode/settings.json << 'EOF'
   {
       "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
       "python.terminal.activateEnvironment": true
   }
   EOF
   ```

3. **更新 `.cursorignore`**（如果需要）：
   在 `.cursorignore` 中，将：
   ```
   .vscode/
   ```
   改为：
   ```
   .vscode/*
   !.vscode/settings.json
   ```
   这样 `.vscode/settings.json` 就不会被忽略。

4. **重启 Cursor**：
   - 完全关闭 Cursor
   - 重新打开项目
   - 现在应该自动使用虚拟环境

### 方法 3：使用 `pyproject.toml` 配置（如果支持）

某些 Python 工具可以自动识别 `pyproject.toml` 中的配置，但 Cursor 主要依赖 `.vscode/settings.json`。

## 验证配置是否生效

### 方法 1：查看状态栏
- 打开任意 `.py` 文件
- 查看 Cursor 底部状态栏
- 应该显示：`Python 3.14.x ('.venv': venv)`

### 方法 2：运行测试脚本
创建一个简单的测试文件 `test_env.py`：
```python
import sys
print(f"Python 路径: {sys.executable}")
print(f"Python 版本: {sys.version}")
```

运行后，输出应该显示 `.venv/bin/python` 而不是系统 Python。

### 方法 3：检查导入
在脚本中尝试导入已安装的包：
```python
import numpy as np
import pandas as pd
print("✅ 成功导入 numpy 和 pandas")
```

如果配置正确，应该不会报 `ModuleNotFoundError`。

## 为什么 Code Runner 和 Cursor 运行按钮行为不同？

1. **Code Runner**：
   - 是第三方扩展
   - 可以独立配置执行器路径
   - 可能已经配置为使用虚拟环境

2. **Cursor 运行按钮**：
   - 使用 VSCode 内置的 Python 运行机制
   - 依赖 Python 扩展选择的解释器
   - 需要明确配置才能使用虚拟环境

## 常见问题

### Q1: 配置后仍然使用全局 Python？
**A**: 
- 检查 `.vscode/settings.json` 路径是否正确
- 重启 Cursor
- 手动通过命令面板重新选择解释器

### Q2: 找不到 `.venv` 目录？
**A**: 
- 确保已经运行过 `uv sync` 或 `uv add <package>`
- 检查 `.gitignore` 是否忽略了 `.venv`（这是正常的）
- 运行 `ls -la .venv` 确认目录存在

### Q3: 多个项目如何管理？
**A**: 
- 每个项目都有独立的 `.vscode/settings.json`
- Cursor 会为每个工作区记住解释器选择
- 打开不同项目时，会自动切换到对应项目的配置

## 推荐工作流程

1. **首次设置**：
   ```bash
   # 1. 使用 uv 安装依赖
   uv add numpy pandas
   
   # 2. 在 Cursor 中选择解释器（方法 1）
   # Cmd+Shift+P → Python: Select Interpreter → ./.venv/bin/python
   ```

2. **日常使用**：
   - 直接点击运行按钮 ▶️
   - 或使用 `uv run python occupational_dna/script.py`

3. **验证环境**：
   - 定期检查状态栏显示的 Python 路径
   - 确保使用的是虚拟环境

## 相关资源

- [VSCode Python 扩展文档](https://code.visualstudio.com/docs/python/python-tutorial)
- [UV 工具文档](https://github.com/astral-sh/uv)
- [Python 虚拟环境最佳实践](https://docs.python.org/3/tutorial/venv.html)

---

## 日期
2026-01-27
