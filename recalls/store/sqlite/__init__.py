"""SQLite backend for the AlertStore port: adapter logic + its SQL dialect."""

from .adapter import SqliteAlertStore

__all__ = ["SqliteAlertStore"]
