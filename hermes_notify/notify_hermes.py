#!/usr/bin/env python3
"""Generic message bus notification sender.

Short-lived connection: connect to bus -> send one message -> disconnect.
Does not register endpoint, does not pollute endpoint_map.

Sender name resolution:
  1. --from manual override (highest priority)
  2. tmux session -> notify.yaml session_aliases lookup
  3. raw tmux session name (fallback)
  4. "notify-hermes" (default)

Usage:
    python3 notify-hermes.py --to <endpoint> "message"
    python3 notify-hermes.py --to <endpoint> --type task_done "Task done"
    python3 notify-hermes.py --to <endpoint> --from "MyName" "message"
    python3 notify-hermes.py --to <endpoint> --body '{"text":"hello"}'
"""
import json
import os
import socket
import struct
import subprocess
import sys
import time
import uuid


def _get_config_path() -> str:
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    return os.path.join(home, "hermes-notify", "notify.yaml")


def _load_config(config_path: str = None) -> dict:
    """Load notify.yaml config. Returns dict with optional session_aliases."""
    path = config_path or _get_config_path()
    config = {}
    if not os.path.exists(path):
        return config

    with open(path) as f:
        content = f.read()

    current_section = None
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            current_section = stripped[:-1].strip()
            if current_section == "session_aliases":
                config["session_aliases"] = {}
            elif current_section == "callbacks":
                config["callbacks"] = []
            continue
        if current_section == "session_aliases" and ":" in stripped:
            key, _, val = stripped.partition(":")
            config["session_aliases"][key.strip()] = val.strip()

    return config


def _resolve_sender_name(override: str = None, config: dict = None) -> str:
    """Determine sender name.

    Priority: --from manual override > session_aliases lookup > tmux session name > default.
    """
    if override:
        return override

    aliases = (config or {}).get("session_aliases", {})

    # Auto-detect from tmux session
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            session = result.stdout.strip()
            if session:
                return aliases.get(session, session)
    except Exception:
        pass

    return "notify-hermes"


def _get_bus_socket_path() -> str:
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    return os.path.join(home, "hermes-bus.sock")


def _ensure_bus_running(socket_path: str):
    """Start bus server if not already running."""
    if os.path.exists(socket_path):
        test = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        test.settimeout(0.5)
        try:
            test.connect(socket_path)
            test.close()
            return
        except Exception:
            try:
                os.unlink(socket_path)
            except Exception:
                pass
        finally:
            test.close()

    # Run bus server via hermes-busd (uses correct Python with package installed)
    subprocess.Popen(
        ["hermes-busd", "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(40):
        time.sleep(0.1)
        if os.path.exists(socket_path):
            break


def _send_frame(sock: socket.socket, msg: dict):
    data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)


def send_notification(endpoint: str, body: dict, socket_path: str = None,
                      from_ep: str = None, config: dict = None) -> bool:
    """Send one message to bus via short-lived connection, then disconnect."""
    sp = socket_path or _get_bus_socket_path()
    _ensure_bus_running(sp)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect(sp)
    except Exception as e:
        print(f"ERROR: Cannot connect to bus: {e}", file=sys.stderr)
        return False

    sender = _resolve_sender_name(from_ep, config)
    msg = {
        "type": "message",
        "to": endpoint,
        "from": sender,
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "body": body,
    }

    try:
        _send_frame(sock, msg)
        sock.settimeout(1.0)
        header = b""
        while len(header) < 4:
            try:
                chunk = sock.recv(4 - len(header))
            except socket.timeout:
                return True
            if not chunk:
                return True
            header += chunk
        if len(header) == 4:
            payload_len = struct.unpack(">I", header)[0]
            payload = b""
            while len(payload) < payload_len:
                try:
                    chunk = sock.recv(payload_len - len(payload))
                except socket.timeout:
                    break
                if not chunk:
                    break
                payload += chunk
            if payload:
                reply = json.loads(payload.decode("utf-8"))
                if reply.get("type") == "error":
                    print(f"WARNING: {reply.get('detail', reply)}", file=sys.stderr)
                    return False
        return True
    except socket.timeout:
        return True
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generic message bus notification sender",
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Target endpoint name (any string, e.g. cli, gateway, my-custom-endpoint)",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Message text (ignored if --body is set)",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="JSON body dict (advanced, overrides positional message)",
    )
    parser.add_argument(
        "--socket",
        default=None,
        help="Custom socket path",
    )
    parser.add_argument(
        "--from",
        dest="from_ep",
        default=None,
        help="Override sender name (default: auto-detect from tmux session or config)",
    )
    parser.add_argument(
        "--type",
        default=None,
        help="Message type for callback matching (any string, matched against notify.yaml match_type)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to notify.yaml config file (for session_aliases)",
    )

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

    success = send_notification(args.to, body, args.socket,
                                from_ep=args.from_ep, config=config)
    if success:
        print(f"OK: notified {args.to}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
