# OpenClaw Bridge

CLI 桥接器，让 OpenClaw 能够通过 MCP 协议操作 Revit。

## Copilot 生态

本仓库是 Copilot For Revit 生态的 OpenClaw 集成组件：

| 仓库 | 定位 | 说明 |
|------|------|------|
| [copilot-for-revit](https://github.com/ryanchan720/copilot-for-revit) | 主框架 | AI 驱动 Revit 的核心平台，支持 MCP 协议。负责插件加载、命令调度、与 AI 对话工具通信。**需先安装此框架才能使用插件。** |
| [copilot-addins-for-revit](https://github.com/ryanchan720/copilot-addins-for-revit) | 开发模板 | AI 友好的插件开发脚手架。提供项目模板、开发规范、最佳实践。适合想要开发自定义命令的用户。 |
| [general-copilot-addins-for-revit](https://github.com/ryanchan720/general-copilot-addins-for-revit) | 通用插件 | 提供现成的常用命令，覆盖元素查询、参数修改、标注创建、视图管理等高频场景。开箱即用。 |
| **本仓库** | OpenClaw 桥接器 | 连接 OpenClaw 和 Revit Copilot 的 CLI 工具，支持健康检查、工具发现、命令执行。 |

**快速选择指南**：
- 想用 AI 控制 Revit → 安装主框架 + 通用插件
- 想开发自己的命令 → 使用开发模板
- 想在飞书/Telegram 等聊天工具里操作 Revit → 安装本桥接器 + 配置 OpenClaw

---

## 用途

这个桥接器让你能够在飞书、Telegram 等聊天工具里用自然语言操作 Revit：

```
你（在飞书）：Revit 在线吗？
Jacob：在线，版本 1.0.0，协议 2024-11-05

你：帮我看看当前项目有哪些门
Jacob：找到 15 种门类型...
```

## 架构

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐      ┌───────────────┐
│   飞书聊天   │ ───► │   OpenClaw   │ ───► │  openclaw-bridge │ ───► │  Revit MCP    │
│  (Ryan)     │      │   (Jacob)    │      │     (CLI)       │      │  (Windows)    │
└─────────────┘      └──────────────┘      └─────────────────┘      └───────────────┘
```

桥接器负责：
1. 连接远程 Revit MCP 服务（HTTP+SSE）
2. 提供 CLI 命令供 OpenClaw 调用
3. 处理协议转换和错误

## 安装

```bash
git clone https://github.com/ryanchan720/openclaw-bridge.git
cd openclaw-bridge
uv sync
```

## 使用

### 配置 MCP 服务器地址

```bash
export REVIT_MCP_URL="http://192.168.x.x:18181"
```

### 检查 Revit 状态

```bash
uv run python -m openclaw_bridge.cli health
```

输出：
```json
{
  "protocol_version": "2024-11-05",
  "server_info": {
    "name": "revit-copilot",
    "version": "1.0.0"
  },
  "session_id": "abc123",
  "status": "healthy"
}
```

### 列出可用工具

```bash
uv run python -m openclaw_bridge.cli tools list
```

### 调用工具

```bash
uv run python -m openclaw_bridge.cli tools call GetEnvInfoCommand --args '{}'
```

## 集成到 OpenClaw

在 OpenClaw 的 workspace 中创建 skill：

```bash
~/.openclaw/workspace/skills/revit-copilot/
├── SKILL.md
├── README.md
└── scripts/
    └── revit_call.py  # 调用本桥接器的脚本
```

详细配置参考 `revit-copilot` skill 的文档。

## 错误处理

所有错误返回 JSON 格式：

```json
{
  "error": true,
  "message": "Connection failed: ...",
  "code": null
}
```

常见错误：
- **Connection failure**: Revit 服务未启动或网络不通
- **Revit is not ready**: Revit 未打开项目文件
- **Tool not found**: 工具名称错误或插件未安装

## 选项

- `--url, -u`: MCP 服务器地址（默认：`http://localhost:18181`）
- `--timeout, -t`: 请求超时秒数（默认：30）

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest
```

## License

MIT License - 详见 [LICENSE](LICENSE) 文件