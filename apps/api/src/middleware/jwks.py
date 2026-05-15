"""JWKS client com cache em memória para validar JWTs do Clerk.

Cache TTL padrão de 1h. Refresh sob demanda quando o `kid` do token não
está no cache (rotação de chave). Singleton via `get_jwks_client()`; testes
podem injetar via `set_jwks_client()`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _CachedJWKS:
    fetched_at: float
    keys: dict[str, dict[str, Any]]


class JWKSClient:
    DEFAULT_TTL_SECONDS = 3600
    DEFAULT_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        url: str,
        *,
        bearer_token: str | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.url = url
        self.bearer_token = bearer_token
        self.ttl_seconds = ttl_seconds
        self._cache: _CachedJWKS | None = None

    async def get_key(self, kid: str) -> dict[str, Any]:
        """Devolve o JWK pra `kid`. Refresh se cache stale ou kid faltando."""
        now = time.time()
        cache = self._cache
        stale = cache is None or now - cache.fetched_at > self.ttl_seconds
        if stale or kid not in cache.keys:
            await self._refresh()
            cache = self._cache

        assert cache is not None
        if kid not in cache.keys:
            raise KeyError(f"JWKS has no key for kid={kid}")
        return cache.keys[kid]

    async def _refresh(self) -> None:
        headers: dict[str, str] = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            resp = await client.get(self.url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        keys = {k["kid"]: k for k in data.get("keys", []) if k.get("kid")}
        self._cache = _CachedJWKS(fetched_at=time.time(), keys=keys)
        logger.info("jwks refreshed: kids=%s", sorted(keys.keys()))


_singleton: JWKSClient | None = None


def get_jwks_client() -> JWKSClient:
    global _singleton
    if _singleton is None:
        url = settings.clerk_jwks_url
        # api.clerk.com exige Bearer com secret key. Frontend API
        # (https://*.clerk.accounts.dev/.well-known/jwks.json) é público.
        bearer = settings.clerk_secret_key if "api.clerk.com" in url else None
        _singleton = JWKSClient(url=url, bearer_token=bearer)
    return _singleton


def set_jwks_client(client: JWKSClient | None) -> None:
    """Override o singleton (para testes)."""
    global _singleton
    _singleton = client
