"""Glue: listens for customer events and pushes them to the GraphQL API."""
from __future__ import annotations

import logging

from .events import CustomerCreated, CustomerUpdated, EventBus
from .graphql_client import GraphQLClient
from .models import Customer

log = logging.getLogger(__name__)

UPSERT_CUSTOMER = """
mutation UpsertCustomer($input: CustomerInput!) {
  upsertCustomer(input: $input) {
    id
    externalId
  }
}
"""


class CustomerSyncHandler:
    """Subscriber that turns domain events into GraphQL mutations."""

    def __init__(self, client: GraphQLClient) -> None:
        self._client = client

    def register(self, bus: EventBus) -> None:
        bus.subscribe(CustomerCreated, self.on_created)
        bus.subscribe(CustomerUpdated, self.on_updated)

    def on_created(self, event: CustomerCreated) -> None:
        self._push(event.customer)

    def on_updated(self, event: CustomerUpdated) -> None:
        log.info("Customer %s changed: %s", event.after.id, sorted(event.changed_fields))
        self._push(event.after)

    def _push(self, customer: Customer) -> None:
        data = self._client.execute(UPSERT_CUSTOMER, {"input": customer.to_graphql_input()})
        log.info("Synced customer %s -> remote id %s",
                 customer.id, data["upsertCustomer"]["id"])
