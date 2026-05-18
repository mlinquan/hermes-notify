#!/usr/bin/env python3
"""Generic message bus notification sender.

Usage:
    python3 notify-hermes.py --to <endpoint> "message"
    python3 notify-hermes.py --to <endpoint> --type task_done "Task done"
    python3 notify-hermes.py --to <endpoint> --from "MyName" "message"
    python3 notify-hermes.py --to <endpoint> --body '{"text":"hello"}'
"""
import json
import os
import subprocess
import sys

from hermes_bus.client import send_message


def _resolve_sender_name(override: str = None, config: dict = None) -> str:
    if override:
        return override
    aliases = (config or {}).get("session_aliases", {})
    try:
        r = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            session = r.stdout.strip()
            return aliases.get(session, session)
    except Exception:
        pass
    return "notify-hermes"


def _load_config(config_path: str = None) -> dict:
    path = config_path or os.path.join(
        os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")),
        "bus-rules.yaml",
    )
    if not os.path.exists(path):
        return {}
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generic message bus notification sender")
    parser.add_argument("--to", required=True, help="Target endpoint name")
    parser.add_argument("message", nargs="?", default=None, help="Message text")
    parser.add_argument("--body", default=None, help="JSON body dict")
    parser.add_argument("--socket", default=None, help="Custom socket path")
    parser.add_argument("--from", dest="from_ep", default=None, help="Override sender name")
    parser.add_argument("--type", default=None, help="Message type for callback matching")
    parser.add_argument("--config", default=None, help="Path to bus-rules.yaml")
    args = parser.parse_args()

    config = _load_config(args.config)

    if args.body:
        try:
            body = json.loads(args.body)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON body: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.message:
        body = {"text": args.message}
    else:
        print("ERROR: Either message text or --body is required", file=sys.stderr)
        sys.exit(1)

    if args.type:
        body["type"] = args.type

    sender = _resolve_sender_name(args.from_ep, config)

    if send_message(args.to, body, args.socket, from_ep=sender):
        print(f"OK: notified {args.to}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
