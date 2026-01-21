"""API routes for ruhroh."""

from app.api import auth, documents, chat, search, admin, config, eval

__all__ = ["auth", "documents", "chat", "search", "admin", "config", "eval"]
