#!/usr/bin/env python3
"""Bus message notification daemon.

Listens to Hermes Bus messages, matches bus-rules.yaml callbacks
by body.type against match_type, then executes the configured command
with MESSAGE / TYPE / FROM as environment variables.
"""
import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

import yaml

HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
_bus_dir = os.path.join(HERMES_HOME, "hermes-bus")
if os.path.isdir(_bus_dir):
    sys.path.insert(0, _bus_dir)
DEFAULT_CONFIG = os.path.join(HERMES_HOME, "bus-rules.yaml")
DEFAULT_SOCKET = os.path.join(HERMES_HOME, "hermes-bus.sock")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bus-notifier")


def load_yaml_config(path: str) -> dict:
    """Load bus-rules.yaml config."""
    if not os.path.exists(path):
        log.error(f"Config file not found: {path}")
        sys.exit(1)
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {"callbacks": []}
    except Exception as e:
        log.error(f"Failed to parse config: {e}")
        sys.exit(1)


def pick_best_rule(msg_type: Optional[str], callbacks: list[dict]) -> Optional[dict]:
    """Find matching callback by body.type exact match against match_type."""
    if not msg_type:
        return None
    for r in callbacks:
        if r.get("match_type") == msg_type:
            return r
    return None


def run_command(rule: dict, msg: dict):
    """Execute the rule's command with MESSAGE/TYPE/FROM as env vars.

    Also writes the full message JSON to stdin for backward compatibility.
    """
    command = rule.get("command", "")
    if not command:
        return

    body = msg.get("body", {})
    msg_type = body.get("type", "") if isinstance(body, dict) else ""
    from_ep = msg.get("from", "unknown")
    msg_json = json.dumps(msg, ensure_ascii=False)

    env = os.environ.copy()
    env["MESSAGE"] = msg_json
    env["TYPE"] = msg_type
    env["FROM"] = from_ep

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
        )
        proc.stdin.write(msg_json.encode())
        proc.stdin.close()
    except Exception as e:
        log.warning(f"Command failed for type [{msg_type}]: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bus message notification daemon")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Config file path")
    parser.add_argument("--socket", default=DEFAULT_SOCKET, help="Bus socket path")
    parser.add_argument("--dry-run", action="store_true", help="Match only, do not execute commands")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Poll interval (seconds)")
    args = parser.parse_args()

    # Load config
    config = load_yaml_config(args.config)
    callbacks = config.get("callbacks", [])
    if not callbacks:
        log.error("No callbacks found in config file")
        sys.exit(1)
    log.info(f"Loaded {len(callbacks)} callbacks")

    # Connect to Bus
    log.info(f"Connecting to Bus: {args.socket}")
    try:
        from hermes_bus.client import BusClient

        client = BusClient("bus-notifier", socket_path=args.socket)
        if not client.connect():
            log.error("Bus connection failed")
            sys.exit(1)
        log.info(f"Bus connected (sid={client.bus_session_id[:8] if client.bus_session_id else '?'})")
    except Exception as e:
        log.error(f"Bus init failed: {e}")
        sys.exit(1)

    # Signal handler
    running = True

    def _shutdown(signum, frame):
        nonlocal running
        log.info(f"Received signal {signum}, exiting...")
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Stats
    total_messages = 0
    total_matched = 0
    total_executed = 0

    # Listen loop
    log.info("Listening for Bus messages...")
    log.info(f"  Callbacks: {len(callbacks)} | Dry-run: {args.dry_run}")
    log.info("-" * 50)

    while running:
        try:
            msgs = client.poll()
        except Exception as e:
            log.warning(f"Poll exception: {e}")
            time.sleep(args.poll_interval)
            continue

        for msg in msgs:
            total_messages += 1

            body = msg.get("body", {})
            text = body.get("text", "") if isinstance(body, dict) else str(body)
            msg_type = body.get("type", None) if isinstance(body, dict) else None
            from_ep = msg.get("from", "unknown")

            # Match by type
            best = pick_best_rule(msg_type, callbacks)
            if best is None:
                continue

            total_matched += 1
            rule_type = best.get("match_type", "unknown")
            command = best.get("command", "")

            log.info(f"Matched [{rule_type}] from={from_ep} text={text[:60]}...")

            if not command:
                log.info(f"  No command configured for type [{rule_type}], skipping")
                continue

            if args.dry_run:
                log.info(f"  [DRY-RUN] Would execute: {command}")
            else:
                log.info(f"  Executing: {command}")
                run_command(best, msg)
                total_executed += 1

        time.sleep(args.poll_interval)

    # Graceful exit
    log.info("-" * 50)
    log.info(f"Stopped. Total messages: {total_messages} | Matched: {total_matched} | Executed: {total_executed}")
    client.disconnect()
    log.info("Exited")


if __name__ == "__main__":
    main()
