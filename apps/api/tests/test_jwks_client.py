"""Cobre o caching/refresh do `JWKSClient` (o stub autouse não exercita o
fetch real). Mockamos `httpx.AsyncClient` no módulo do JWKS pra contar calls.
"""

import pytest

from src.middleware import jwks as jwks_module
from src.middleware.jwks import JWKSClient, set_jwks_client


class _MockResp:
    def __init__(self, data: dict) -> None:
        self.data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self.data


class _MockHttpxClient:
    """Captura calls pra contar fetches; devolve JWKS controlável via classe."""

    keys: list[dict] = []
    calls: list[str] = []

    def __init__(self, *a, **kw) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a) -> None:
        return None

    async def get(self, url: str, headers=None) -> _MockResp:
        type(self).calls.append(url)
        return _MockResp({"keys": list(type(self).keys)})


@pytest.fixture
def mock_httpx(monkeypatch):
    _MockHttpxClient.calls = []
    _MockHttpxClient.keys = [
        {"kid": "k1", "kty": "RSA", "use": "sig", "alg": "RS256", "n": "AAAA", "e": "AQAB"},
    ]
    monkeypatch.setattr(jwks_module.httpx, "AsyncClient", _MockHttpxClient)
    set_jwks_client(None)  # invalida singleton da fixture autouse
    yield _MockHttpxClient


async def test_jwks_client_caches_after_first_fetch(mock_httpx) -> None:
    client = JWKSClient(url="https://example.com/jwks")
    a = await client.get_key("k1")
    b = await client.get_key("k1")
    assert a is b
    assert len(mock_httpx.calls) == 1, "segunda call não devia bater na rede"


async def test_jwks_client_refreshes_on_kid_miss(mock_httpx) -> None:
    client = JWKSClient(url="https://example.com/jwks")
    await client.get_key("k1")
    assert len(mock_httpx.calls) == 1

    # Adiciona k2 ao "lado servidor" e pede k2 — deve forçar refresh.
    mock_httpx.keys = mock_httpx.keys + [
        {"kid": "k2", "kty": "RSA", "use": "sig", "alg": "RS256", "n": "BBBB", "e": "AQAB"},
    ]
    k2 = await client.get_key("k2")
    assert k2["kid"] == "k2"
    assert len(mock_httpx.calls) == 2

    # k1 ainda no cache (mesmo refresh trouxe k1+k2 juntos)
    k1 = await client.get_key("k1")
    assert k1["kid"] == "k1"
    assert len(mock_httpx.calls) == 2


async def test_jwks_client_raises_on_unknown_kid(mock_httpx) -> None:
    client = JWKSClient(url="https://example.com/jwks")
    with pytest.raises(KeyError):
        await client.get_key("k_does_not_exist")
