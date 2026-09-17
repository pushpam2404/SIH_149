"""Standard application/debug logging — separate from the audit ledger.

This is for developer-facing diagnostics (stack traces, subprocess output,
timing). Evidentiary/audit records of user actions belong in
app.core.audit.ledger instead, never here.
"""
from __future__ import annotations

import logging
import sys

from app.config.settings import LOG_LEVEL

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
