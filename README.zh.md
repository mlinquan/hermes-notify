# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

<p align="center"><img src="assets/avator_default_png8.png" width="500" alt="Snow"></p>

**在 Hermes 消息生态系统中的角色：** hermes-notify 是 **CLI 发送层** —— 两个命令（`notify-hermes`、`notify-agent`）用于将消息注入生态系统。它只负责发送，不负责接收或处理。生态系统中的另外两个包：

- [hermes-bus](https://github.com/mlinquan/hermes-bus) — **传输守护进程**，通过 Unix Socket 在端点之间路由 JSON 消息
- [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin) — **接收端 agent 插件**，消费总线消息并路由到终端输出、LLM 上下文注入或命令执行

三者协作：**notify → bus → plugin**。路由规则配置在 `~/.hermes/bus-rules.yaml`。

---

## Hermes 消息生态系统

![Hermes Bus Ecosystem Architecture](https://raw.githubusercontent.com/mlinquan/hermes-bus-plugin/main/docs/architecture.svg)

生态系统分为四层：

```
第1层 — CLI / 用户空间（本包）
  notify-hermes ──→ hermes-bus (Unix Socket)
  notify-agent  ──→ tmux session (send-keys)

第2层 — 传输
  hermes-bus 守护进程 — JSON 路由、会话管理

第3层 — Agent / 插件
  hermes-bus-plugin — print · context · command · channel 路由

第4层 — Gateway / 平台
  平台适配器 — WeChat · Feishu · WeCom · DingTalk → 用户
```

| 层 | 包 | 角色 |
|----|-----|------|
| 1 — CLI | **hermes-notify** *(本包)* | 将消息发送到生态系统 |
| 2 — 传输 | **hermes-bus** | 在端点之间路由 JSON 消息 |
| 3 — 插件 | **hermes-bus-plugin** | 消费消息：终端输出、LLM 上下文、命令执行、channel 路由 |
| 4 — Gateway | *(下游)* | 平台适配器将回复投递给最终用户。**零 agent 代码改动** |

---

## 安装

```bash
pip install hermes-notify
```

或从源码安装：

```bash
git clone https://github.com/mlinquan/hermes-notify.git
cd hermes-notify && pip install -e .
```

---

## `notify-hermes` — 通过总线发送

通过短连接 Unix Socket（`hermes_bus.client.send_message`）将 JSON 消息发送到任意总线端点。消息由总线守护进程路由到目标端点。路由处理（print、context 注入、命令执行）由接收端的 `hermes-bus-plugin` 负责。

### 语法

```bash
notify-hermes --to <endpoint> [选项] "消息文本"
notify-hermes --to <endpoint> --body '{"text":"hello","key":"value"}'
```

### 参数

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--to` | 是 | — | 目标总线端点名称（如 `lead-agent`、`hermes-bus`、`worker-alpha`） |
| `"消息"` | * | — | 纯文本消息（位置参数，最后一个参数）。与 `--body` 互斥 |
| `--body` | * | — | 完整 JSON body 字符串。与位置参数互斥 |
| `--type` | 否 | 无 | 应用层消息类型（见下表） |
| `--channel` | 否 | 无 | 回复路由令牌：`platform:chat_id` 或 `platform`（回退到 `*_HOME_CHANNEL` 环境变量） |
| `--from` | 否 | 自动 | 覆盖发送者名称。默认从 tmux session 通过 `bus-rules.yaml` 的 `role_map` 自动检测 |
| `--socket` | 否 | 自动 | 自定义 Unix socket 路径。默认：`$HERMES_BUS_ROOT/hermes-bus.sock` |
| `--config` | 否 | 自动 | `bus-rules.yaml` 路径。默认：`$HERMES_HOME/bus-rules.yaml` |

\* `"消息"` 或 `--body` 二选一，不能同时使用。

### `--type` 值

> 以下为常用约定 —— `--type` 接受任意字符串，`bus-rules.yaml` 精确匹配。

| `--type` | 含义 | 接收端行为（通过 bus-rules.yaml） |
|----------|------|--------------------------------|
| `directive` | 任务指派（协调者 → 工人） | context=true（静默注入） |
| `ack` | 收到确认 | print=true（终端输出） |
| `task_start` | 任务开始 | context=true |
| `progress` | 中间进度更新 | context=true |
| `task_done` | 任务完成 | print=true + context=true + command（音频 + gateway-forward） |
| `plan_ready` | 方案已就绪 | print=true + context=true + command |
| `task_error` | 错误/升级 | print=true + context=true + command |
| `need_decision` | 需要决策 | print=true + context=true + command |

### `--channel` 值

| 值 | 解析为 |
|----|--------|
| `feishu:oc_abc123` | 飞书，直接发送到 `oc_abc123` 会话 |
| `wecom:ww456` | 企微，直接发送到 `ww456` 会话 |
| `dingtalk:cid789` | 钉钉，直接发送到 `cid789` 会话 |
| `feishu` | 飞书，回退到 `FEISHU_HOME_CHANNEL` 环境变量 |
| `wecom` | 企微，回退到 `WECOM_HOME_CHANNEL` 环境变量 |

channel 令牌是**不透明的路由字符串**。Agent 原样透传，不做解释。只有最终投递点的 bus-plugin 才对其操作。

### 消息体组装

使用 `"消息文本"`（位置参数）时：
```json
{"text": "消息文本", "type": "task_done", "channel": "feishu:oc_abc123"}
```

使用 `--body` 时：
```json
{"text": "hello", "type": "ack", "custom_field": "value"}
```

`--type` 和 `--channel` 会合并到 body 字典中。`--body` 中已定义的字段优先。

### 示例

```bash
# 简单确认
notify-hermes --to lead-agent --type ack "收到，开始工作"

# 任务完成，带 channel 回复路由
notify-hermes --to lead-agent --type task_done \
  --channel feishu:oc_abc123 \
  "认证中间件重构完成。5/5 端点已迁移。"

# 进度更新（静默 —— 仅上下文注入，终端不显示）
notify-hermes --to lead-agent --type progress \
  --channel feishu:oc_abc123 \
  "第2/4阶段：已提取 token 验证模块"

# 错误升级，带 channel
notify-hermes --to lead-agent --type task_error \
  --channel wecom_ops \
  "生产环境故障 —— 数据库连接池耗尽"

# 完整 JSON body 自定义负载
notify-hermes --to lead-agent \
  --body '{"text":"部署完成","type":"task_done","version":"2.1.0","commit":"abc123"}'

# 自定义发送者名称
notify-hermes --to lead-agent --type ack --from ci-pipeline "构建 #142 通过"
```

---

## `notify-agent` — 发送到 tmux 会话

通过 `send-keys` 直接向 tmux 会话发送文本。不经过总线。用于同一台机器内 Agent 之间的直接通信。

### 语法

```bash
notify-agent [--from 发送者] <tmux-session-名称> "消息文本"
```

### 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `<session>` | 是 | 目标 **tmux session 名称**（`tmux new-session -s` 传入的名称）。这不是总线端点或 agent 名称 |
| `--from` | 否 | 发送者显示名称。省略时从 session 名称自动检测 |
| `"消息"` | 是 | 纯文本消息（位置参数，最后一个参数） |

### 示例

```bash
# 启动两个 agent 会话
tmux new-session -d -s lead-agent   'claude'
tmux new-session -d -s worker-alpha 'claude'

# 发送消息
notify-agent lead-agent "任务队列为空，等待下一条指令"

# 带显式发送者
notify-agent --from worker-alpha lead-agent "构建完成，3 个测试通过"
```

**重要：** 目标必须是运行中的 tmux 会话。需要总线路由消息时使用 `notify-hermes`，由 `hermes-bus-plugin` 处理。

---

## 配置

路由规则、角色映射和发送者自动检测配置在 `~/.hermes/bus-rules.yaml` 中。完整规则格式参见 [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin)。

### 角色映射（用于 `--from` 自动检测）

```yaml
# bus-rules.yaml
role_map:
  lead-agent:   {name: "Lead",    color: "bold_cyan"}
  worker-alpha: {name: "Alpha",   color: "bold_yellow"}
  worker-beta:  {name: "Beta",    color: "bold_magenta"}
  unknown:      {name: "Unknown", color: "white"}

default_sender: notify-agent
```

省略 `--from` 时，`notify-hermes` 读取当前 tmux session 名称，在 `role_map` 中查找，使用映射的 `name` 作为发送者。

### 技能注册

作为 Hermes 插件安装时，`hermes-notify` 注册 `notify-cli` 技能——Agent 可通过 `snow_search` 发现 CLI 通知工具（`notify-hermes`、`notify-agent`），无需阅读源码或手册页。

---

## 快速开始

```bash
# 1. 安装三个包
pip install hermes-bus hermes-notify hermes-bus-plugin

# 2. 启动总线守护进程
hermes-busd start

# 3. 启动 agent 会话
tmux new-session -d -s lead-agent   'claude'
tmux new-session -d -s worker-alpha 'claude'

# 4. 发送消息
notify-hermes --to lead-agent --type ack "Hello from worker-alpha"
notify-agent --from worker-alpha lead-agent "直接消息，不经总线"

# 5. 检查总线状态
hermes-busd status
```

---

## 架构

```
notify-hermes ──→ hermes-bus (Unix Socket) ──→ hermes-bus-plugin (agent)
notify-agent  ──→ tmux send-keys ──→ 目标 session 终端

消息路由（print / context 注入 / 命令执行）
由 hermes-bus-plugin 通过 ~/.hermes/bus-rules.yaml 处理
```
