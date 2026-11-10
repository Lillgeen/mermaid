"""Persistence layer. Publishes events after successful writes."""
from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from .events import CustomerCreated, CustomerUpdated, EventBus
from .models import Customer


class CustomerNotFound(LookupError):
    pass


class CustomerRepository(ABC):
    """Abstract interface: the rest of the code depends on this, not on SQLite.

    Swap in Postgres, an in-memory dict, etc. without touching anything else.
    """

    @abstractmethod
    def get(self, customer_id: int) -> Customer: ...

    @abstractmethod
    def add(self, customer: Customer) -> Customer: ...

    @abstractmethod
    def update(self, customer: Customer) -> Customer: ...


class SqliteCustomerRepository(CustomerRepository):
    def __init__(self, conn: sqlite3.Connection, bus: EventBus) -> None:
        self._conn = conn
        self._bus = bus
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL,
                phone      TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )

    def get(self, customer_id: int) -> Customer:
        row = self._conn.execute(
            "SELECT id, name, email, phone, updated_at FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if row is None:
            raise CustomerNotFound(customer_id)
        return self._from_row(row)

    def add(self, customer: Customer) -> Customer:
        with self._conn:  # commits on success, rolls back on error
            cur = self._conn.execute(
                "INSERT INTO customers (name, email, phone, updated_at) VALUES (?, ?, ?, ?)",
                (customer.name, customer.email, customer.phone, customer.updated_at.isoformat()),
            )
        saved = customer.with_changes(id=cur.lastrowid, updated_at=customer.updated_at)
        self._bus.publish(CustomerCreated(customer=saved))
        return saved

    def update(self, customer: Customer) -> Customer:
        before = self.get(customer.id)
        with self._conn:
            self._conn.execute(
                "UPDATE customers SET name = ?, email = ?, phone = ?, updated_at = ? WHERE id = ?",
                (customer.name, customer.email, customer.phone,
                 customer.updated_at.isoformat(), customer.id),
            )
        # Publish only AFTER the commit, so subscribers never see data that
        # might still be rolled back.
        event = CustomerUpdated(before=before, after=customer)
        if event.changed_fields:
            self._bus.publish(event)
        return customer

    @staticmethod
    def _from_row(row: tuple) -> Customer:
        id_, name, email, phone, updated_at = row
        return Customer(id=id_, name=name, email=email, phone=phone,
                        updated_at=datetime.fromisoformat(updated_at))
