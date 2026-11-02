def test_register_login_refresh_me(client):
    r = client.post("/api/auth/register", json={"email": "A@Example.com", "password": "supersecret1", "full_name": "A"})
    assert r.status_code == 201
    assert client.post("/api/auth/register", json={"email": "a@example.com", "password": "supersecret1"}).status_code == 409

    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "supersecret1"})
    assert r.status_code == 200
    tokens = r.json()

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "a@example.com" and me.json()["role"] == "user"

    r = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    # An access token must not work as a refresh token and vice versa
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}).status_code == 401


def test_bad_credentials_and_short_password(client):
    client.post("/api/auth/register", json={"email": "b@example.com", "password": "supersecret1"})
    assert client.post("/api/auth/login", json={"email": "b@example.com", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": "c@example.com", "password": "short"}).status_code == 422


def test_admin_routes_require_admin(client):
    assert client.get("/api/admin/statistics").status_code == 401
    t = client.post("/api/auth/register", json={"email": "d@example.com", "password": "supersecret1"}).json()
    h = {"Authorization": f"Bearer {t['access_token']}"}
    assert client.get("/api/admin/statistics", headers=h).status_code == 403
