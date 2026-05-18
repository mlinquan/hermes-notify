# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

配置驱动的通知路由器 — 规则匹配、上下文注入、命令执行。

独立于传输层。从 stdin 或 Bus hook 接收消息，按 `notify.yaml` 规则匹配后执行配置的命令。

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

# 处理回调消息（从 stdin 读取）
echo '{"body":{"type":"task_done","text":"done"}}' | hermes-callback
```

## 配置

`notify.yaml` 定义规则，每条指定 `match_type` 和执行命令：

```yaml
callbacks:
  - match_type: task_error
    print: false
    context: true
    command: "notify-send 'Task failed'"

  - match_type: task_done
    print: false
    context: true
    command: "afplay ~/sounds/done.mp3"
```

两个布尔字段控制行为：`print`（终端打印）、`context`（注入 LLM 上下文）。

`command` 执行时传入环境变量：`MESSAGE`（完整JSON）、`TYPE`（消息类型）、`FROM`（发送者）。同时 stdin 传入原始消息 JSON。

## 架构

```
stdin / Bus hook ──→ bus_callback.py ──→ notify.yaml 规则匹配
                                              │
                                          匹配成功？
                                          ├─ 是 → 执行命令
                                          └─ 否 → 静默

notify-hermes — 总线消息发送 CLI
notify-agent  — tmux 通知发送 CLI
```
