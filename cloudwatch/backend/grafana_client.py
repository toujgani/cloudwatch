import time
from typing import Any
import requests
from .config import settings


class GrafanaClient:
    def __init__(self):
        self.base_url = settings.GRAFANA_URL.rstrip("/")
        self.timeout = 15

    @property
    def configured(self) -> bool:
        return bool(self.base_url and settings.GRAFANA_API_TOKEN)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if settings.GRAFANA_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GRAFANA_API_TOKEN}"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self.configured:
            raise RuntimeError("Grafana API is not configured. Set GRAFANA_URL and GRAFANA_API_TOKEN.")
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=self.timeout,
            verify=settings.GRAFANA_VERIFY_SSL,
            **kwargs,
        )
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    def health(self) -> Any:
        return self._request("GET", "/api/health")

    def query_datasource(self, datasource_uid: str, queries: list[dict], from_ms: int, to_ms: int) -> Any:
        payload = {"from": str(from_ms), "to": str(to_ms), "queries": queries}
        for query in payload["queries"]:
            query.setdefault("datasource", {"uid": datasource_uid})
        return self._request("POST", "/api/ds/query", json=payload)


def now_ms() -> int:
    return int(time.time() * 1000)


def hours_range_ms(hours: int) -> tuple[int, int]:
    end = now_ms()
    return end - hours * 60 * 60 * 1000, end
