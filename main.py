"""Demo: update a customer in SQLite and watch it get sent over GraphQL.

Run against a real API:
    GRAPHQL_ENDPOINT=https://example.com/graphql GRAPHQL_TOKEN=... python main.py
Without GRAPHQL_ENDPOINT, a fake client prints the request instead.
"""
import json
import logging
import os
import sqlite3

from customer_sync.events import EventBus
from customer_sync.graphql_client import GraphQLClient, HttpGraphQLClient
from customer_sync.models import Customer
from customer_sync.repository import SqliteCustomerRepository
from customer_sync.sync import CustomerSyncHandler


class PrintingGraphQLClient(GraphQLClient):
    """Stand-in for a real server: prints the request, returns a fake answer."""

    def __init__(self) -> None:
        self._next_id = 1000

    def execute(self, query: str, variables: dict | None = None) -> dict:
        print("--> GraphQL request variables:", json.dumps(variables, indent=2))
        self._next_id += 1
        return {"upsertCustomer": {"id": str(self._next_id),
                                   "externalId": variables["input"]["externalId"]}}


def build_client() -> GraphQLClient:
    endpoint = os.environ.get("GRAPHQL_ENDPOINT")
    if endpoint:
        return HttpGraphQLClient(endpoint, token=os.environ.get("GRAPHQL_TOKEN"))
    return PrintingGraphQLClient()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Wiring ("composition root"): the only place that knows the concrete classes.
    bus = EventBus()
    CustomerSyncHandler(build_client()).register(bus)
    repo = SqliteCustomerRepository(sqlite3.connect(":memory:"), bus)

    alice = repo.add(Customer(id=None, name="Alice", email="alice@example.com"))
    repo.update(alice.with_changes(email="alice@newmail.com", phone="+46 70 123 45 67"))
    repo.update(repo.get(alice.id))  # nothing changed -> no event, no request


if __name__ == "__main__":
    main()
