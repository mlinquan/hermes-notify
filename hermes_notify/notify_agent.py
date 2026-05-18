#!/usr/bin/env python3
"""Generic tmux notification tool — sends messages to tmux sessions via send-keys.

Sender name resolution:
  1. --from override (highest priority)
  2. notify.yaml default_sender config value

Usage:
    python3 notify-agent.py --from <sender> <session> <message>
    python3 notify-agent.py --from <sender> --simple <session> <message>
    python3 notify-agent.py <session> <message>               # sender from config or none
"""
import os
import sys
import subprocess
import time


def _get_config_path() -> str:
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    return os.path.join(home, "bus-rules.yaml")


def _load_default_sender(config_path: str = None) -> str:
    """Load default_sender from notify.yaml config. Falls back to empty string."""
    path = config_path or _get_config_path()
    if not os.path.exists(path):
        return ""

    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("default_sender:"):
                return stripped.split(":", 1)[1].strip()
    return ""


def main():
    simple_mode = False
    sender = None
    config_path = None
    args = sys.argv[1:]

    # Parse --config
    if args and args[0] == '--config':
        if len(args) >= 2:
            config_path = args[1]
            args = args[2:]
        else:
            print("Usage: --config <path>", file=sys.stderr)
            sys.exit(1)

    # Parse --from parameter
    if args and args[0] == '--from':
        if len(args) >= 2:
            sender = args[1]
            args = args[2:]
        else:
            print("Usage: --from <sender_name>", file=sys.stderr)
            sys.exit(1)

    if args and args[0] == '--simple':
        simple_mode = True
        args = args[1:]

    if len(args) < 2:
        print("Usage: python3 notify-agent.py [--config <path>] [--from <sender>] [--simple] <session> <message>",
              file=sys.stderr)
        sys.exit(1)

    session = args[0]

    if sender:
        message = sender + ': ' + ' '.join(args[1:])
    else:
        default = _load_default_sender(config_path)
        if default:
            message = default + ': ' + ' '.join(args[1:])
        else:
            message = ' '.join(args[1:])

    # Clear input area first (C-c to interrupt any running task)
    subprocess.run(['tmux', 'send-keys', '-t', session, 'C-c'], timeout=3)
    time.sleep(0.5)

    # Send message
    subprocess.run(['tmux', 'send-keys', '-t', session, message], timeout=3)
    time.sleep(0.3)

    # Triple Enter to submit
    for _ in range(3):
        subprocess.run(['tmux', 'send-keys', '-t', session, 'Enter'], timeout=3)
        time.sleep(0.2)

    print(f'OK: notified {session}')


if __name__ == "__main__":
    main()
