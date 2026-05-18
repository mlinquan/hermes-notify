"""Hermes notification plugin — rule matching, audio playback, display control.

Transport-agnostic.
Reads messages from stdin JSON or Bus hook, matches against notify.yaml rules.

Multi-backend architecture:
 stdin / Bus hook -> bus_callback.py -> notify.yaml rules -> execute callback

Current backends:
 - bus (subprocess hook mode)
Backends to add:
 - tmux, stdout, webhook
"""
