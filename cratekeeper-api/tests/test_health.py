def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_mounts_endpoint(client):
    r = client.get("/api/v1/health/mounts")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert "roots" in body
