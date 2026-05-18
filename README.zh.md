# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

配置驱动的通知工具集 — 总线消息发送器和 tmux 通知。

与 `hermes-bus` 和 `hermes-bus-plugin` 配合使用。路由规则配置在 `~/.hermes/bus-rules.yaml`。

## 这是什么？

hermes-notify 提供两个 CLI 工具：

- **`notify-hermes`** — 发送消息到总线任意端点（短连接，底层调用 `hermes_bus.client.send_message`）
- **`notify-agent`** — 通过 tmux send-keys 发送通知

路由处理（打印、上下文注入、命令执行）由 `hermes-bus-plugin` 负责。

### 快速开始

1. 安装：`pip install hermes-notify`
2. 在 `~/.hermes/bus-rules.yaml` 配置路由规则（详见 [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin)）
3. 发送消息：`notify-hermes --to my-service --type task_done "Hello"`
4. 插件匹配 `match_type: task_done` 并处理

## 安装

```bash
pip install hermes-notify
```

或从源码安装：

```bash
git clone https://github.com/mlinquan/hermes-notify.git
cd hermes-notify && pip install -e .
```

## CLI

```bash
# 发送总线消息到任意端点
notify-hermes --to my-service --type task_done "任务完成"
notify-hermes --to my-service --type progress "50%"
notify-hermes --to my-service --type ack "收到"

# 发送 tmux 通知
notify-agent mysession "开工"
notify-agent --simple mysession "通知消息"
```

路由处理由 hermes-bus-plugin 负责，详见 https://github.com/mlinquan/hermes-bus-plugin

## 配置

路由规则定义在 `~/.hermes/bus-rules.yaml`，由 [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin) 处理。详见其 README。

session_aliases 和 default_sender 同样配置在 `bus-rules.yaml`：

```yaml
session_aliases:
  session-1: alias-1
  session-2: alias-2

default_sender: notify-agent
```

## 架构

```
notify-hermes ──→ hermes-bus (Unix Socket)
notify-agent  ──→ tmux send-keys

消息路由（打印/注入/命令）由 hermes-bus-plugin 通过 ~/.hermes/bus-rules.yaml 处理
```
