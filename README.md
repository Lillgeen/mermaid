# Customer sync: event-driven integration over GraphQL

A small practice project for object-oriented Python. When a customer is
created or updated in the database, an event is published, and a subscriber
sends the customer to a GraphQL API.

Uses only the Python standard library (3.10+).

```
SqliteCustomerRepository.update()
        │  commit, then publish
        ▼
     EventBus ──► CustomerUpdated(before, after)
        │
        ▼
CustomerSyncHandler.on_updated()
        │  mutation UpsertCustomer($input: CustomerInput!)
        ▼
   GraphQLClient.execute()  ──HTTP POST──►  remote GraphQL API
```

## Files

| File | Role | OOP idea |
|---|---|---|
| `customer_sync/models.py` | `Customer` | Immutable dataclass, validation in `__post_init__` |
| `customer_sync/events.py` | `Event`, `CustomerCreated`, `CustomerUpdated`, `EventBus` | Inheritance, Observer pattern |
| `customer_sync/repository.py` | `CustomerRepository` (ABC), `SqliteCustomerRepository` | Abstraction, Repository pattern |
| `customer_sync/graphql_client.py` | `GraphQLClient` (ABC), `HttpGraphQLClient` | Polymorphism: real, fake and printing clients are interchangeable |
| `customer_sync/sync.py` | `CustomerSyncHandler` | Dependency injection: it gets a client and doesn't care which kind |
| `main.py` | Wires everything together | Composition root |

## Run

```bash
python main.py                    # fake client prints what would be sent
GRAPHQL_ENDPOINT=https://your-api/graphql GRAPHQL_TOKEN=... python main.py
python -m unittest -v
```

## Ideas to practice next

1. **Transactional outbox:** right now, if the process crashes after the DB
   commit but before the HTTP call, the update is lost. Write events to an
   `outbox` table in the same transaction, and have a separate worker send them.
2. **Async:** make the handler run in a background thread or queue so a slow
   API doesn't slow down `update()`.
3. **Send only what changed:** use `CustomerUpdated.changed_fields` to send a
   partial update mutation.
4. **Real database triggers:** in Postgres, use `LISTEN/NOTIFY` or CDC
   (e.g. Debezium) so updates made outside this app also produce events.
