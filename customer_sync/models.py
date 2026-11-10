"""Domain model."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone


@dataclass(frozen=True)
class Customer:
    """A customer as stored in our database.

    frozen=True makes instances immutable: to "change" a customer you create a
    new copy with `with_changes(...)`. That makes it safe to pass customers
    around inside events without anyone mutating them behind your back.
    """

    id: int | None
    name: str
    email: str
    phone: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        # Validation lives with the data it protects.
        if not self.name.strip():
            raise ValueError("Customer name must not be empty")
        if "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email!r}")

    def with_changes(self, **changes) -> "Customer":
        """Return a copy with some fields changed and a fresh updated_at."""
        changes.setdefault("updated_at", datetime.now(timezone.utc))
        return replace(self, **changes)

    def to_graphql_input(self) -> dict:
        """Shape the customer the way the remote GraphQL API expects it."""
        return {
            "externalId": str(self.id),
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "updatedAt": self.updated_at.isoformat(),
        }
