def test_health_check_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    # Env vars are stubbed with truthy fake values in conftest.py, so both
    # configured flags should read True -- this is really asserting the
    # endpoint reads the same config module the rest of the app does, not
    # that real credentials are present.
    assert body["groq_configured"] is True
    assert body["supabase_configured"] is True