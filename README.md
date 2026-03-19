# OpenClaw Bridge

CLI 桥接器，让 OpenClaw 能够通过 MCP 协议操作 Revit。

## Copilot 生态

本仓库是 Copilot For Revit 生态的 OpenClaw 集成组件：

| 仓库 | 定位 | 说明 |
|------|------|------|
| [copilot-for-revit](https://github.com/ryanchan720/copilot-for-revit) | 主框架 | AI 驱动 Revit 的核心平台，支持 MCP 协议。负责插件加载、命令调度、与 AI 对话工具通信。**需先安装此框架才能使用插件。** |
| [copilot-addins-for-revit](https://github.com/ryanchan720/copilot-addins-for-revit) | 开发模板 | AI 友好的插件开发脚手架。提供项目模板、开发规范、最佳实践。适合想要开发自定义命令的用户。 |
| [general-copilot-addins-for-revit](https://github.com/ryanchan720/general-copilot-addins-for-revit) | 通用插件 | 提供现成的常用命令，覆盖元素查询、参数修改、标注创建、视图管理等高频场景。开箱即用。 |
| **本仓库** | OpenClaw 桥接器 | 连接 OpenClaw 和 Copilot for Revit 的 CLI 工具，支持健康检查、工具发现、命令执行。 |
| [copilot-for-revit-skill](https://github.com/ryanchan720/copilot-for-revit-skill) | OpenClaw Skill | OpenClaw skill 包，配合本桥接器使用。安装后可在聊天工具中直接操作 Revit。 |

**快速选择指南**：
- 想用 AI 控制 Revit → 安装主框架 + 通用插件
- 想开发自己的命令 → 使用开发模板
- 想直接用现成功能 → 安装通用插件
- 想在飞书/Telegram 等聊天工具里操作 Revit → 安装 Copilot + 通用插件 + 本桥接器 + 配置 OpenClaw

---

## 物理架构

```
┌────────────────────────────────────┐         ┌────────────────────────────────────┐
│         Linux 主机                  │         │         Windows 主机                │
│                                    │         │                                    │
│  ┌─────────────┐  ┌──────────────┐ │         │  ┌──────────────┐  ┌────────────┐  │
│  │   飞书/聊天  │  │   OpenClaw   │ │         │  │    Revit     │  │  Copilot   │  │
│  │             │─►│             │ │         │  │              │  │  for Revit │  │
│  └─────────────┘  └──────┬───────┘ │         │  └──────────────┘  └─────┬──────┘  │
│                          │         │         │                          │         │
│                   ┌──────▼───────┐ │  HTTP   │                   ┌──────▼──────┐  │
│                   │   本桥接器    │ │◄───────┼───────────────────►│  MCP 服务   │  │
│                   │openclaw-bridge│ │  18181 │                   │  (端口18181)│  │
│                   └──────────────┘ │         │                   └────────────┘  │
│                                    │         │                                    │
└────────────────────────────────────┘         └────────────────────────────────────┘
```

**要点**：
- OpenClaw 和本桥接器运行在 **Linux 主机**
- Revit 和 Copilot for Revit 运行在 **Windows 主机**
- 两台主机需要网络互通（Linux 能访问 Windows 的 18181 端口）

---

## 用途

这个桥接器让你能够在飞书、Telegram 等聊天工具里用自然语言操作 Revit：

```
你（在飞书）：Revit 在线吗？
OpenClaw：在线，版本 1.0.0，协议 2024-11-05

你：帮我看看当前项目有哪些门
OpenClaw：找到 15 种门类型...
```

## 安装

### 前置条件

1. **Windows 端**已安装并配置好：
   - Revit 2019-2024
   - [Copilot for Revit](https://github.com/ryanchan720/copilot-for-revit)
   - [通用插件](https://github.com/ryanchan720/general-copilot-addins-for-revit)（可选）
   - MCP 服务已配置为远程访问（详见[配置 MCP 远程访问](#配置-mcp-远程访问)）

2. **Linux 端**已安装：
   - Python 3.10+
   - [uv](https://docs.astral.sh/uv/)

### 安装步骤

```bash
git clone https://github.com/ryanchan720/openclaw-bridge.git
cd openclaw-bridge
uv sync
```

---

## 使用

### 配置 MCP 服务器地址

```bash
export REVIT_MCP_URL="http://<WINDOWS_IP>:18181"
```

将 `<WINDOWS_IP>` 替换为运行 Revit 的 Windows 主机 IP 地址。

> **注意**：Copilot for Revit 默认只监听 `localhost`，需要额外配置才能远程访问。详见下方"配置 MCP 远程访问"章节。

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

---

## 配置 MCP 远程访问

Copilot for Revit 默认只监听 `localhost`，要让 Linux 主机能访问，需要：

1. **修改 Copilot 代码**：将 MCP 监听前缀改为 `http://+:18181/`
2. **配置 Windows URL ACL**：
   ```powershell
   netsh http add urlacl url=http://+:18181/ user=<Windows用户名>
   ```
3. **放行防火墙**：
   ```powershell
   netsh advfirewall firewall add rule name="Revit MCP 18181" dir=in action=allow protocol=TCP localport=18181
   ```

详细说明请参考 [Copilot for Revit 的 README - 常见问题](https://github.com/ryanchan720/copilot-for-revit#常见问题)。

---

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

---

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
- **Connection failure**: Copilot 服务未启动或网络不通
- **Revit is not ready**: Revit 未打开项目文件
- **Tool not found**: 工具名称错误或插件未安装

---

## 选项

- `--url, -u`: MCP 服务器地址（默认：`http://localhost:18181`）
- `--timeout, -t`: 请求超时秒数（默认：30）

---

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest
```

---

## License

MIT License - 详见 [LICENSE](LICENSE) 文件