import json
import sqlite3
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from customer_sync.events import CustomerUpdated, EventBus
from customer_sync.graphql_client import GraphQLClient, GraphQLError, HttpGraphQLClient
from customer_sync.models import Customer
from customer_sync.repository import SqliteCustomerRepository
from customer_sync.sync import CustomerSyncHandler


class FakeGraphQLClient(GraphQLClient):
    """Test double: records calls instead of doing HTTP."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, query, variables=None):
        self.calls.append((query, variables))
        return {"upsertCustomer": {"id": "r1", "externalId": variables["input"]["externalId"]}}


def make_app():
    bus = EventBus()
    client = FakeGraphQLClient()
    CustomerSyncHandler(client).register(bus)
    repo = SqliteCustomerRepository(sqlite3.connect(":memory:"), bus)
    return repo, client, bus


class CustomerTests(unittest.TestCase):
    def test_rejects_bad_email(self):
        with self.assertRaises(ValueError):
            Customer(id=None, name="Bob", email="nope")

    def test_with_changes_returns_new_object(self):
        c = Customer(id=1, name="Bob", email="b@x.se")
        c2 = c.with_changes(name="Robert")
        self.assertEqual(c.name, "Bob")
        self.assertEqual(c2.name, "Robert")


class SyncFlowTests(unittest.TestCase):
    def test_create_and_update_are_pushed(self):
        repo, client, _ = make_app()
        c = repo.add(Customer(id=None, name="Alice", email="a@x.se"))
        repo.update(c.with_changes(email="alice@x.se"))

        self.assertEqual(len(client.calls), 2)
        sent = client.calls[-1][1]["input"]
        self.assertEqual(sent["email"], "alice@x.se")
        self.assertEqual(sent["externalId"], str(c.id))

    def test_no_event_when_nothing_changed(self):
        repo, client, _ = make_app()
        c = repo.add(Customer(id=None, name="Alice", email="a@x.se"))
        repo.update(repo.get(c.id))
        self.assertEqual(len(client.calls), 1)  # only the create

    def test_changed_fields(self):
        repo, _, bus = make_app()
        seen = []
        bus.subscribe(CustomerUpdated, seen.append)
        c = repo.add(Customer(id=None, name="Alice", email="a@x.se"))
        repo.update(c.with_changes(name="Alicia", phone="123"))
        self.assertEqual(seen[0].changed_fields, {"name", "phone"})

    def test_failing_subscriber_does_not_break_others(self):
        bus = EventBus()
        seen = []
        bus.subscribe(CustomerUpdated, lambda e: 1 / 0)
        bus.subscribe(CustomerUpdated, seen.append)
        c = Customer(id=1, name="A", email="a@x.se")
        with self.assertLogs("customer_sync.events", "ERROR"):
            bus.publish(CustomerUpdated(before=c, after=c.with_changes(name="B")))
        self.assertEqual(len(seen), 1)


class HttpClientTests(unittest.TestCase):
    """Spins up a real local HTTP server that speaks GraphQL-over-JSON."""

    def setUp(self):
        self.requests = []
        self.response = {"data": {"ok": True}}
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                test.requests.append((dict(self.headers), json.loads(self.rfile.read(length))))
                body = json.dumps(test.response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = HttpGraphQLClient(
            f"http://127.0.0.1:{self.server.server_port}/graphql", token="secret"
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_sends_query_variables_and_token(self):
        data = self.client.execute("query { ok }", {"a": 1})
        self.assertEqual(data, {"ok": True})
        headers, body = self.requests[0]
        self.assertEqual(body, {"query": "query { ok }", "variables": {"a": 1}})
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_graphql_errors_raise(self):
        self.response = {"data": None, "errors": [{"message": "boom"}]}
        with self.assertRaisesRegex(GraphQLError, "boom"):
            self.client.execute("query { ok }")


if __name__ == "__main__":
    unittest.main()
