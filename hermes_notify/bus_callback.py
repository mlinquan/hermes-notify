#!/usr/bin/env python3
"""Bus message callback router.

Spawned by Bus Server as post-route hook.
Reads message JSON from stdin, matches callbacks config rules, executes callbacks.
"""
import json
import logging
import os
import subprocess
import sys
import time
from typing import Optional

HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
_notify_dir = os.path.join(HERMES_HOME, "hermes-notify")
if os.path.isdir(_notify_dir):
    sys.path.insert(0, _notify_dir)

CONFIG_PATH = os.path.join(HERMES_HOME, "hermes-notify", "notify.yaml")

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    filename=os.path.join(HERMES_HOME, "logs", "errors.log"),
    filemode="a",
)
log = logging.getLogger("bus.callback")

# Consecutive failure count: rule_key -> (fail_count, last_fail_time, suppressed)
_failure_tracker: dict[str, list] = {}
FAILURE_THRESHOLD = 3
FAILURE_SUPPRESS_SECONDS = 300  # suppress for 5 minutes after threshold


def load_yaml_config(path: str) -> dict:
    """Load YAML config file (no third-party deps)."""
    if not os.path.exists(path):
        log.warning(f"Config file not found: {path}")
        return {"callbacks": []}

    with open(path) as f:
        content = f.read()

    config = {"callbacks": []}
    current_rule = None

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if any(stripped.startswith(f"- {p}:") for p in
               ["match_type", "command"]):
            current_rule = {}
            config["callbacks"].append(current_rule)
            key, _, val = stripped.lstrip("- ").partition(":")
            current_rule[key.strip()] = val.strip().strip("'\"")

        elif current_rule is not None and indent >= 4:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")

            if key == "priority":
                current_rule[key] = int(val)
            elif key in ("print", "context"):
                current_rule[key] = val.lower() in ("true", "yes", "1")
            elif key == "command":
                current_rule[key] = os.path.expanduser(val)
            elif key == "match_type":
                current_rule[key] = val
            else:
                current_rule[key] = val

    return config


def should_suppress(rule_key: str) -> bool:
    """Check if this rule should be suppressed (too many consecutive failures)."""
    if rule_key not in _failure_tracker:
        return False
    count, last_fail, suppressed = _failure_tracker[rule_key]
    if suppressed and time.time() - last_fail < FAILURE_SUPPRESS_SECONDS:
        return True
    if suppressed and time.time() - last_fail >= FAILURE_SUPPRESS_SECONDS:
        # Unsuppress
        del _failure_tracker[rule_key]
        return False
    return False


def record_failure(rule_key: str):
    """Record one failure."""
    if rule_key not in _failure_tracker:
        _failure_tracker[rule_key] = [1, time.time(), False]
    else:
        _failure_tracker[rule_key][0] += 1
        _failure_tracker[rule_key][1] = time.time()
        if _failure_tracker[rule_key][0] >= FAILURE_THRESHOLD:
            _failure_tracker[rule_key][2] = True
            log.warning(
                f"callback rule [{rule_key}] failed {FAILURE_THRESHOLD} consecutive times, "
                f"suppressed for {FAILURE_SUPPRESS_SECONDS}s"
            )


def record_success(rule_key: str):
    """Reset failure count after success."""
    _failure_tracker.pop(rule_key, None)


def pick_best_rule(text: str, msg_type: Optional[str],
                   callbacks: list[dict]) -> Optional[dict]:
    """Select best matching rule. Single message triggers once only.

    Match body.type against match_type, pick highest priority.
    Returns None if no match.
    """
    if msg_type:
        type_matches = [r for r in callbacks if r.get("match_type") == msg_type]
        if type_matches:
            return min(type_matches, key=lambda r: r.get("priority", 100))

    return None


def run_callback(rule: dict, message: dict):
    """Execute callback command with MESSAGE/TYPE/FROM as env vars."""
    command = rule.get("command", "")
    if not command:
        return

    body = message.get("body", {})
    msg_type = body.get("type", "") if isinstance(body, dict) else ""
    from_ep = message.get("from", "unknown")
    msg_json = json.dumps(message, ensure_ascii=False)

    rule_key = f"{rule.get('match_type','')}:{rule.get('command','')}"

    if should_suppress(rule_key):
        return

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
        # Let it run asynchronously (no wait)
        record_success(rule_key)
    except Exception as e:
        log.warning(f"callback [{rule_key}] failed: {type(e).__name__}: {e}")
        record_failure(rule_key)


def main():
    # read stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        msg = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("stdin is not valid JSON")
        return
    except Exception as e:
        log.warning(f"stdin read failed: {e}")
        return

    # Load config
    config = load_yaml_config(CONFIG_PATH)
    callbacks = config.get("callbacks", [])
    if not callbacks:
        return

    # Extract text and type
    body = msg.get("body", {})
    text = body.get("text", "") if isinstance(body, dict) else str(body)
    msg_type = body.get("type", None) if isinstance(body, dict) else None

    # type exact match, single trigger
    best = pick_best_rule(text, msg_type, callbacks)
    if best:
        run_callback(best, msg)


if __name__ == "__main__":
    main()
