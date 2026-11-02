def test_health_check_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    # env vars are stubbed in conftest.py.
    # this checks health reads shared config, not real credentials.
    assert body["groq_configured"] is True
    assert body["supabase_configured"] is True