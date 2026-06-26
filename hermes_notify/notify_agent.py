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


def _load_role_map(config_path: str = None) -> dict:
    """Load role_map from bus-rules.yaml. Falls back to empty dict."""
    path = config_path or _get_config_path()
    if not os.path.exists(path):
        return {}
    try:
        import yaml
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("role_map", {}) if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _lookup_role(from_ep: str, role_map: dict) -> str:
    """Resolve a sender token into its role_map display name.

    Accepts either a session key (e.g. "shiyinru") or an existing display name.
    Returns the token unchanged if not found in role_map.
    """
    if not from_ep:
        return from_ep
    role = role_map.get(from_ep, {})
    if role:
        return role.get("name", from_ep)
    for cfg in role_map.values():
        if cfg.get("name") == from_ep:
            return cfg.get("name", from_ep)
    return from_ep


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

    # Parse --from parameter (--from may appear before or after --to)
    while args and args[0] == '--from':
        if len(args) >= 2:
            sender = args[1]
            args = args[2:]
        else:
            print("Usage: --from <sender_name>", file=sys.stderr)
            sys.exit(1)

    # Parse --to parameter (alias for the positional <session>)
    if args and args[0] == '--to':
        if len(args) >= 2:
            session_via_to = args[1]
            args = args[2:]
        else:
            print("Usage: --to <session>", file=sys.stderr)
            sys.exit(1)
    else:
        session_via_to = None

    if args and args[0] == '--simple':
        simple_mode = True
        args = args[1:]

    if len(args) < 1 and not session_via_to:
        print("Usage: python3 notify-agent.py [--config <path>] [--from <sender>] [--to <session>] [--simple] <session> <message>",
              file=sys.stderr)
        sys.exit(1)

    # session: --to takes precedence, else the first positional arg
    if session_via_to:
        session = session_via_to
    else:
        session = args[0]
        args = args[1:]

    role_map = _load_role_map(config_path)
    if sender:
        name = _lookup_role(sender, role_map)
        message = f"[{name}]: " + ' '.join(args)
    else:
        default = _lookup_role(_load_default_sender(config_path), role_map)
        if default:
            message = f"[{default}]: " + ' '.join(args)
        else:
            message = ' '.join(args)

    if not message:
        print("Usage: a message text is required", file=sys.stderr)
        sys.exit(1)

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
