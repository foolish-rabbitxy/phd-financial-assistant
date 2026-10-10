"""`python3 -m src.web [run|setup]` — the finance dashboard (Alpaca paper account, view-only)."""

from __future__ import annotations

import getpass
import json
import logging
import os
import sys
from pathlib import Path

from .auth import hash_password, password_problem

CONFIG_PATH = Path.home() / ".config" / "finance-dashboard" / "config.json"
DEFAULTS = {"dashboard_password_hash": "", "public_url": "http://192.168.50.62:8501",
            "home_url": "http://192.168.50.62/",
            "listen_host": "0.0.0.0", "listen_port": 8501}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)


def setup() -> None:
    cfg = load_config()
    pw = getpass.getpass("Finance dashboard password (8+ characters): ")
    problem = password_problem(pw, getpass.getpass("Repeat it: "))
    if problem:
        sys.exit(problem + " Nothing saved.")
    cfg["dashboard_password_hash"] = hash_password(pw)
    save_config(cfg)
    print(f"Saved to {CONFIG_PATH} (readable only by you). Restart: systemctl --user restart finance-dashboard")


def run() -> None:
    cfg = load_config()
    if not cfg["dashboard_password_hash"]:
        sys.exit("Not set up yet: run `python3 -m src.web setup` first.")
    from src.utils.mail import send_email

    from . import picks
    from .alpaca_data import Alpaca
    from .server import App, serve
    alpaca = Alpaca()
    held = lambda: [p["symbol"] for p in alpaca.positions()]
    serve(App(cfg, alpaca, send_email, lambda: picks.compute(held), save_config=save_config))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": run, "setup": setup}.get(cmd, lambda: sys.exit(f"unknown command {cmd}"))()


if __name__ == "__main__":
    main()
