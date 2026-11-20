from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from service_osint.discovery.base import DiscoveryResult
from service_osint.discovery.config import DiscoveryConfig
from service_osint.discovery.providers.serper import SerperProvider
from service_osint.discovery.router import discover


def _test_config(**overrides: str | None) -> DiscoveryConfig:
    base = dict(
        searxng_url=None,
        serper_api_key=None,
        brave_api_key=None,
        linkup_api_key=None,
        firecrawl_api_key=None,
        tavily_api_key=None,
        exa_api_key=None,
        jina_api_key=None,
        opencorporates_api_token=None,
    )
    base.update(overrides)
    return DiscoveryConfig(**base)


def test_serper_provider_formats_connection_error() -> None:
    provider = SerperProvider(_test_config(serper_api_key="test-key"))
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    with patch("service_osint.discovery.providers.serper.httpx.Client", return_value=mock_client):
        result = provider.search("john doe", limit=3)

    assert result.error
    assert "Serper" in result.error
    assert result.hits == []


def test_serper_provider_unavailable_without_key() -> None:
    provider = SerperProvider(_test_config())
    assert not provider.available()
    result = provider.search("test")
    assert "SERPER_API_KEY" in (result.error or "")


def test_discover_runs_available_providers_in_parallel_and_preserves_order() -> None:
    class FakeProvider:
        def __init__(self, name: str) -> None:
            self.name = name

        def available(self) -> bool:
            return True

        def search(self, query: str, *, limit: int) -> DiscoveryResult:
            import time

            time.sleep(0.05)
            return DiscoveryResult(query=query, provider=self.name)

    provider_names = (
        "searxng",
        "serper",
        "tavily",
        "exa",
        "brave",
        "linkup",
        "firecrawl",
        "duckduckgo",
    )

    with patch(
        "service_osint.discovery.router.build_providers",
        return_value=[FakeProvider(name) for name in provider_names],
    ):
        import time

        started = time.perf_counter()
        results = discover("test query", limit=2)
        elapsed = time.perf_counter() - started

    assert [result.provider for result in results] == list(provider_names)
    assert elapsed < 0.25
