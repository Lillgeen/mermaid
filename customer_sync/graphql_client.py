"""GraphQL transport. Uses only the standard library (urllib)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


class GraphQLError(Exception):
    """The server answered, but reported errors in the `errors` field."""

    def __init__(self, errors: list[dict]) -> None:
        self.errors = errors
        super().__init__("; ".join(e.get("message", str(e)) for e in errors))


class GraphQLClient(ABC):
    @abstractmethod
    def execute(self, query: str, variables: dict | None = None) -> dict:
        """Run a query/mutation and return the `data` part of the response."""


class HttpGraphQLClient(GraphQLClient):
    def __init__(
        self,
        endpoint: str,
        token: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self.endpoint = endpoint
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff_seconds

    def execute(self, query: str, variables: dict | None = None) -> dict:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        for attempt in range(1, self._max_retries + 1):
            request = urllib.request.Request(self.endpoint, data=payload, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                    body = json.loads(resp.read())
                break
            except (urllib.error.URLError, TimeoutError):
                # Network problems are often temporary: retry with backoff.
                if attempt == self._max_retries:
                    raise
                time.sleep(self._backoff * 2 ** (attempt - 1))

        if body.get("errors"):
            raise GraphQLError(body["errors"])
        return body["data"]
