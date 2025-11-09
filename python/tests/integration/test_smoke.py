import httpx


def test_health_smoke():
    resp = httpx.get("http://localhost:8080/health", timeout=5.0)
    assert resp.status_code == 200


def test_metrics_smoke():
    resp = httpx.get("http://localhost:8080/metrics", timeout=5.0)
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
