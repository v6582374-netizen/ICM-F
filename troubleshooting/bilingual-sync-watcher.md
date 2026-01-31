# 双语同步：文件监听方案

## 适用场景

当我们需要在中文版本修改后自动更新英文版本，但不希望每次提交才同步时，使用文件监听方案。

## 核心机制

- 监听 `zh/main.tex` 与 `zh/sections/*.tex`
- 中文文件保存后自动同步到英文版本
- 英文同步仅针对发生变更的文件

## 前置条件

- 已配置 DeepSeek API Key
- Python 3 可用

## 使用方法

在项目根目录执行：

```
python3 code/watch_sync.py
```

保持该进程运行后，保存中文文件会触发同步：

- `zh/sections/*.tex` → `en/sections/*.tex`
- `zh/main.tex` → `en/main.tex`（标题翻译 + 章节输入列表同步）

## 环境变量

必需：

```
export DEEPSEEK_API_KEY="你的key"
```

可选：

```
export DEEPSEEK_MODEL="deepseek-chat"
export DEEPSEEK_API_BASE="https://api.deepseek.com/v1"
```

## 常见问题

### 1) 同步无反应

- 确认监听进程仍在运行
- 确认修改的是 `zh/` 目录下的 `.tex` 文件
- 确认已保存文件

### 2) 报错 `DEEPSEEK_API_KEY is not set`

- 说明环境变量未设置或终端未加载
- 重新执行导出命令后再启动监听进程

### 3) 频繁限流或失败

- 等待 1–2 分钟后重试
- 适当降低改动频率
