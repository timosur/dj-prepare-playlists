def test_get_anthropic_settings_default(client):
    r = client.get("/api/v1/settings/anthropic")
    assert r.status_code == 200
    body = r.json()
    assert body == {"configured": False, "model": "claude-sonnet-4-6", "prompt_caching": True}


def test_set_anthropic_secret_roundtrip(client):
    r = client.put("/api/v1/settings/anthropic", json={"api_key": "sk-test", "prompt_caching": False})
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["prompt_caching"] is False
    # secret value never returned
    assert "api_key" not in body

    overview = client.get("/api/v1/settings").json()
    assert overview["anthropic_configured"] is True


def test_genre_buckets_seeded_and_replaceable(client):
    r = client.get("/api/v1/settings/genre-buckets")
    assert r.status_code == 200
    seeded = r.json()
    assert len(seeded) > 5
    # order is preserved
    assert [b["sort_order"] for b in seeded] == sorted([b["sort_order"] for b in seeded])

    replacement = {
        "buckets": [
            {"name": "Only One", "genre_tags": ["all"], "is_fallback": True},
        ]
    }
    r = client.put("/api/v1/settings/genre-buckets", json=replacement)
    assert r.status_code == 200
    out = r.json()
    assert len(out) == 1
    assert out[0]["name"] == "Only One"


def test_tag_vocabularies_readonly(client):
    r = client.get("/api/v1/settings/tag-vocabularies")
    assert r.status_code == 200
    body = r.json()
    assert "feelgood" in body["mood"]
    assert "floorfiller" in body["function"]


def test_fs_roots_persisted(client, tmp_path):
    p = str(tmp_path)
    r = client.put("/api/v1/settings/fs-roots", json={"roots": [p]})
    assert r.status_code == 200
    assert r.json()["roots"] == [p]
    assert client.get("/api/v1/settings/fs-roots").json()["roots"] == [p]
