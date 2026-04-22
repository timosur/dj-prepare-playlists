"""Tidal session management — login, token persistence, and auto-refresh."""

from __future__ import annotations

import json
from pathlib import Path

import tidalapi

SESSION_FILE = Path(__file__).resolve().parent.parent / "tidal-session.json"


def get_session() -> tidalapi.Session:
    """Return an authenticated Tidal session.

    Tries to load an existing session from *tidal-session.json*.  If the file
    does not exist or the stored session is invalid, raises an error telling
    the user to run the auth flow first.
    """
    session = tidalapi.Session()

    if SESSION_FILE.exists():
        session.login_session_file(SESSION_FILE)
        if session.check_login():
            return session

    raise RuntimeError(
        "Not logged in to Tidal. Run `python -m tidal_mcp.auth` first to authenticate."
    )


def run_auth() -> None:
    """Interactive OAuth login — opens a browser link for the user."""
    session = tidalapi.Session()
    session.login_oauth_simple()

    if session.check_login():
        # Persist the session for later use
        session.save_session_to_file(SESSION_FILE)
        print(f"Logged in as: {session.user.first_name} {session.user.last_name}")
        print(f"Session saved to {SESSION_FILE}")
    else:
        print("Login failed.")
        raise SystemExit(1)
