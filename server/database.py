"""Compatibility shim — prefer `db.session` imports in new code."""

from db.session import check_database, get_engine

__all__ = ["check_database", "get_engine"]
