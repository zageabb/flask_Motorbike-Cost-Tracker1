"""UDA prefix check with isolated in-memory database."""
from app import create_app

def test_uda_and_lan_login():
    app = create_app({"TESTING": True,"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:","SEED_SAMPLE_DATA": False})
    client = app.test_client()
    local = client.get("/auth/login")
    assert local.status_code == 200
    assert '<base href="/">' in local.get_data(as_text=True)
    headers = {"X-Forwarded-Prefix": "/apps/motorbike-cost-tracker",
               "X-Forwarded-Host": "tanyaanne.ddns.net",
               "X-Forwarded-Proto": "https"}
    proxied = client.get("/auth/login",headers=headers)
    assert proxied.status_code == 200
    html = proxied.get_data(as_text=True)
    assert '<base href="/apps/motorbike-cost-tracker/">' in html
    assert '/apps/motorbike-cost-tracker/static/app.css' in html
