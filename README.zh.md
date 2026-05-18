# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

配置驱动的通知发送器 — 通过总线发送消息和 tmux 通知。

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

`notify-hermes` 的分发端点和路由规则由 `~/.hermes/bus-rules.yaml` 控制（详见 [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin)）。

## 架构

```
notify-hermes ──→ hermes-bus (Unix Socket)
notify-agent  ──→ tmux send-keys

总线消息的路由 → 打印/注入/命令 由 hermes-bus-plugin 处理
```
