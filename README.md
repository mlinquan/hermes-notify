# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

A config-driven notification toolkit for Hermes Agent — CLI senders for bus messages and tmux notifications.

Works with `hermes-bus` and `hermes-bus-plugin`. Route rules live in `~/.hermes/bus-rules.yaml`.

## What is this?

hermes-notify provides two CLI tools:

- **`notify-hermes`** — send messages to any bus endpoint (short-lived connection via `hermes_bus.client.send_message`)
- **`notify-agent`** — send messages to tmux sessions via `send-keys`

Route processing (print, context injection, command execution) is handled by `hermes-bus-plugin`.

### Quickstart

1. Install: `pip install hermes-notify`
2. Configure route rules in `~/.hermes/bus-rules.yaml` (see [hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin))
3. Send a message: `notify-hermes --to my-service --type task_done "Hello"`
4. The plugin matches `match_type: task_done` and handles it

## Install

```bash
pip install hermes-notify
```

Or from source:

```bash
git clone https://github.com/mlinquan/hermes-notify.git
cd hermes-notify && pip install -e .
```

## CLI

```bash
# Send a message to any bus endpoint
notify-hermes --to my-service --type task_done "Task completed"
notify-hermes --to my-service --type progress "50% done"
notify-hermes --to my-service --type ack "Received"

# Send a notification to a tmux session
notify-agent mysession "Start working"
notify-agent --simple mysession "FYI: something happened"

# Route processing is handled by hermes-bus-plugin
# See https://github.com/mlinquan/hermes-bus-plugin
```

## Configuration

Route rules are defined in `~/.hermes/bus-rules.yaml` and processed by
[hermes-bus-plugin](https://github.com/mlinquan/hermes-bus-plugin).
See its README for the full rule format.

Session aliases and the default sender name are also configured in `bus-rules.yaml`:

## Architecture

```
notify-hermes ──→ hermes-bus (Unix Socket)
notify-agent  ──→ tmux send-keys

Message routing (print/inject/command) is handled by hermes-bus-plugin
via ~/.hermes/bus-rules.yaml.
```

## Session Aliases

Map tmux session names to human-readable sender names in `bus-rules.yaml`:

```yaml
session_aliases:
  session-1: alias-1
  session-2: alias-2

default_sender: notify-agent
```
