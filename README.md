# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

<p align="center"><img src="assets/avator_default_png8.png" width="500" alt="Snow"></p>

**Role in the Hermes messaging ecosystem:** hermes-notify is the **CLI sender layer** — two commands (`notify-hermes`, `notify-agent`) for injecting messages into the ecosystem. It sends; it does not receive or process. The other two packages in the ecosystem are:

- [hermes-bus](https://github.com/mlinquan/hermes-bus) — **transport daemon** that routes JSON messages between endpoints via Unix Socket
- [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin) — **receive-side agent plugin** that consumes bus messages and routes them to terminal output, LLM context injection, or command execution

Together: **notify → bus → plugin**. Route rules live in `~/.hermes/bus-rules.yaml`.

---

## Hermes Messaging Ecosystem

![Hermes Bus Ecosystem Architecture](https://raw.githubusercontent.com/mlinquan/hermes-bus-plugin/main/docs/architecture.svg)

The ecosystem has four layers:

```
Layer 1 — CLI / User Space (this package)
  notify-hermes ──→ hermes-bus (Unix Socket)
  notify-agent  ──→ tmux session (send-keys)

Layer 2 — Transport
  hermes-bus daemon — JSON routing, session management

Layer 3 — Agent / Plugin
  hermes-bus-plugin — print · context · command · channel routing

Layer 4 — Gateway / Platform
  Platform adapters — WeChat · Feishu · WeCom · DingTalk → Users
```

| Layer | Package | Role |
|-------|---------|------|
| 1 — CLI | **hermes-notify** *(this package)* | Send messages into the ecosystem |
| 2 — Transport | **hermes-bus** | Route JSON messages between endpoints |
| 3 — Plugin | **hermes-bus-plugin** | Consume messages: terminal output, LLM context, commands, channel routing |
| 4 — Gateway | *(downstream)* | Platform adapters deliver replies to end users. **Zero agent code changes** |

---

## Install

```bash
pip install hermes-notify
```

Or from source:

```bash
git clone https://github.com/mlinquan/hermes-notify.git
cd hermes-notify && pip install -e .
```

---

## `notify-hermes` — Send Through the Bus

Sends a JSON message to any bus endpoint via short-lived Unix Socket connection (`hermes_bus.client.send_message`). The message is routed by the bus daemon to the target endpoint. Route processing (print, context injection, command execution) is handled by `hermes-bus-plugin` on the receiving end.

### Syntax

```bash
notify-hermes --to <endpoint> [options] "message text"
notify-hermes --to <endpoint> --body '{"text":"hello","key":"value"}'
```

### Parameters

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--to` | yes | — | Target bus endpoint name (e.g. `lead-agent`, `hermes-bus`, `worker-alpha`) |
| `"message"` | * | — | Plain text message (positional, last argument). Mutually exclusive with `--body` |
| `--body` | * | — | Full JSON body dict as a string. Mutually exclusive with positional message |
| `--type` | no | none | Application-level message type (see table below) |
| `--channel` | no | none | Reply routing token: `platform:chat_id` or `platform` (falls back to `*_HOME_CHANNEL` env var) |
| `--from` | no | auto | Override sender name. Auto-detected from tmux session via `role_map` in `bus-rules.yaml` |
| `--socket` | no | auto | Custom Unix socket path. Default: `$HERMES_BUS_ROOT/hermes-bus.sock` |
| `--config` | no | auto | Path to `bus-rules.yaml`. Default: `$HERMES_HOME/bus-rules.yaml` |

\* Either `"message"` or `--body` is required, but not both.

### `--type` values

> The values below are common conventions — `--type` accepts any string, `bus-rules.yaml` matches them exactly.

| `--type` | Meaning | Receiver behavior (via bus-rules.yaml) |
|----------|---------|---------------------------------------|
| `directive` | Task assignment (coordinator → worker) | context=true (silent injection) |
| `ack` | Acknowledgement | print=true (terminal only) |
| `task_start` | Task started | context=true |
| `progress` | Intermediate progress update | context=true |
| `task_done` | Task completed | print=true + context=true + command (audio + gateway-forward) |
| `plan_ready` | Plan ready for review | print=true + context=true + command |
| `task_error` | Error / escalation | print=true + context=true + command |
| `need_decision` | Decision needed | print=true + context=true + command |

### `--channel` values

| Value | Resolves to |
|-------|-------------|
| `feishu:oc_abc123` | Feishu, chat `oc_abc123` directly |
| `wecom:ww456` | WeCom, chat `ww456` directly |
| `dingtalk:cid789` | DingTalk, chat `cid789` directly |
| `feishu` | Feishu, fallback to `FEISHU_HOME_CHANNEL` env var |
| `wecom` | WeCom, fallback to `WECOM_HOME_CHANNEL` env var |

The channel token is an **opaque routing string**. Agents pass it through unmodified. Only the bus-plugin at final delivery acts on it.

### Message body assembly

When using `"message text"` (positional):
```json
{"text": "message text", "type": "task_done", "channel": "feishu:oc_abc123"}
```

When using `--body`:
```json
{"text": "hello", "type": "ack", "custom_field": "value"}
```

`--type` and `--channel` are merged into the body dict. `--body` takes precedence for fields it already defines.

### Examples

```bash
# Simple acknowledgement
notify-hermes --to lead-agent --type ack "Received, starting work"

# Task completion with channel for reply routing
notify-hermes --to lead-agent --type task_done \
  --channel feishu:oc_abc123 \
  "Auth middleware refactor complete. 5/5 endpoints migrated."

# Progress update (silent — context injection only, no terminal noise)
notify-hermes --to lead-agent --type progress \
  --channel feishu:oc_abc123 \
  "Phase 2 of 4: extracted token validation module"

# Error escalation with channel
notify-hermes --to lead-agent --type task_error \
  --channel wecom_ops \
  "Production outage detected — database connection pool exhausted"

# Full JSON body for custom payloads
notify-hermes --to lead-agent \
  --body '{"text":"Deploy complete","type":"task_done","version":"2.1.0","commit":"abc123"}'

# Custom sender name override
notify-hermes --to lead-agent --type ack --from ci-pipeline "Build #142 passed"
```

---

## `notify-agent` — Send to a tmux Session

Sends text directly to a tmux session via `send-keys`. Does NOT go through the bus. Used for direct inter-agent communication within the same machine.

### Syntax

```bash
notify-agent [--from SENDER] [--to SESSION] <session> "message text"
```

### Parameters

| Argument | Required | Description |
|----------|----------|-------------|
| `--to` | no | Target tmux session name (alternative to positional `<session>`) |
| `--from` | no | Sender display name. Resolved through `role_map` if a session key is provided. Auto-detected from session name if omitted |
| `<session>` | yes* | Target tmux session name (positional, alternative to `--to`) |
| `"message"` | yes | Plain text message (positional, last argument) |

\* Either `--to` or positional `<session>` is required.

### Message Format

Messages are formatted as `[{sender}]: {text}` where `{sender}` is resolved through `role_map`:

```bash
# If role_map has: worker-alpha: {name: "Alpha", ...}
notify-agent --from worker-alpha --to lead-agent "Hello"
# Sends: [Alpha]: Hello
```

### Examples

```bash
# Start two agent sessions
tmux new-session -d -s lead-agent   'claude'
tmux new-session -d -s worker-alpha 'claude'

# Send a message (auto-detect sender from current session)
notify-agent lead-agent "Task queue is empty, ready for next assignment"

# With explicit sender (resolved through role_map)
notify-agent --from worker-alpha --to lead-agent "Build complete, 3 tests passing"

# Using --to parameter
notify-agent --from worker-alpha --to lead-agent "Direct message via --to"
```

**Important:** The target must be a running tmux session. Use `notify-hermes` for bus-routed messages that can be processed by `hermes-bus-plugin`.

---

## Configuration

Route rules, role mappings, and sender auto-detection are configured in `~/.hermes/bus-rules.yaml`. See [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin) for the full rule format.

### Role mapping (for `--from` auto-detection)

```yaml
# bus-rules.yaml
role_map:
  lead-agent:   {name: "Lead",    color: "bold_cyan"}
  worker-alpha: {name: "Alpha",   color: "bold_yellow"}
  worker-beta:  {name: "Beta",    color: "bold_magenta"}
  unknown:      {name: "Unknown", color: "white"}

default_sender: notify-agent
```

When `--from` is omitted, `notify-hermes` reads the current tmux session name, looks it up in `role_map`, and uses the mapped `name` as the sender.

### Skill Registration

When installed as a Hermes plugin, `hermes-notify` registers the `notify-cli` skill — agents can discover CLI notification tools (`notify-hermes`, `notify-agent`) via `snow_search` without reading source code or man pages.

---

## Quickstart

```bash
# 1. Install all three packages
pip install hermes-bus hermes-notify hermes-bus-plugin

# 2. Start the bus daemon
hermes-busd start

# 3. Start agent sessions
tmux new-session -d -s lead-agent   'claude'
tmux new-session -d -s worker-alpha 'claude'

# 4. Send messages
notify-hermes --to lead-agent --type ack "Hello from worker-alpha"
notify-agent --from worker-alpha lead-agent "Direct message, no bus"

# 5. Check bus status
hermes-busd status
```

---

## Architecture

```
notify-hermes ──→ hermes-bus (Unix Socket) ──→ hermes-bus-plugin (agent)
notify-agent  ──→ tmux send-keys ──→ target session terminal

Message routing (print / context injection / command execution)
is handled by hermes-bus-plugin via ~/.hermes/bus-rules.yaml.
```
