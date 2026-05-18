# hermes-notify

[English](./README.md) | [中文](./README.zh.md)

A config-driven notification router for Hermes Agent — rule matching, context injection, audio playback, and custom command execution.

Transport-agnostic. Reads messages from stdin or a Bus hook, matches against `notify.yaml` rules, and executes the configured action.

## What is this?

hermes-notify is a **message router** for the Hermes Agent ecosystem. When a message arrives (from a bus, a script, or stdin), it checks the message type against your `notify.yaml` rules. If a rule matches, it executes the configured command — anything from a macOS notification to a Slack webhook.

### Quickstart

1. Install: `pip install hermes-notify`
2. Create a `notify.yaml` config file with a rule (see Configuration below)
3. Send a message: `notify-hermes --to my-service --type task_done "Hello"`
4. The callback matches `match_type: task_done` and runs your command

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

# Process a callback message from stdin
echo '{"body":{"type":"task_done","text":"done"}}' | hermes-callback
```

## Configuration

Messages are routed by `notify.yaml`. Each callback rule specifies a `match_type` and a `command` to execute:

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

Two boolean fields control behavior: `print` (terminal output), `context` (inject into LLM context).

The `command` field receives these environment variables:
- `MESSAGE` — full message JSON
- `TYPE` — message type
- `FROM` — sender endpoint name
- Stdin — raw message JSON (for backward compatibility)

Example callback scripts are bundled in `examples/`:

```bash
examples/macos-notify.py    # macOS notification via osascript
examples/play-sound.py      # Play random sound via afplay  
examples/slack-notify.sh    # Slack webhook (set SLACK_WEBHOOK_URL)
```

## Architecture

```
stdin / Bus hook ──→ bus_callback.py ──→ notify.yaml rules
                                              │
                                         Match?
                                        ├─ yes → execute command
                                        └─ no  → silent

notify-hermes — Bus message sender
notify-agent  — tmux notification sender
```

## Session Aliases

Map tmux session names to human-readable sender names in `notify.yaml`:

```yaml
session_aliases:
  session-1: alias-1
  session-2: alias-2

default_sender: notify-agent
```
