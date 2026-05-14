from __future__ import annotations


class BoardError(Exception):
    """Expected ai-board failure shown as a CLI error."""


class BoardLockError(BoardError):
    pass


class BoardSchemaError(BoardError):
    pass


class ScopeConflictError(BoardError):
    pass


class TaskNotFoundError(BoardError):
    pass
