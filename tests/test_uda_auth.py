from app import User, create_app, db


def make_app():
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SEED_SAMPLE_DATA": False,
            "UDA_AUTH_ENABLED": True,
            "UDA_REQUIRED_GROUP": "Personal",
            "UDA_TRUSTED_PROXY_IPS": {"127.0.0.1", "::1"},
            "UDA_USER_ALIASES": {},
        }
    )


def test_trusted_uda_user_is_provisioned_and_signed_in():
    app = make_app()
    try:
        client = app.test_client()
        response = client.get(
            "/",
            headers={"X-UDA-User": "proxy.user@example.com", "X-UDA-Groups": "Personal"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/home")
        dashboard = client.get(
            "/home",
            headers={"X-UDA-User": "proxy.user@example.com", "X-UDA-Groups": "Personal"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert b"UDA: proxy.user@example.com" in dashboard.data
        with app.app_context():
            assert User.query.filter_by(email="proxy.user@example.com").count() == 1
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_direct_client_cannot_spoof_uda_identity():
    app = make_app()
    try:
        client = app.test_client()
        response = client.get(
            "/",
            headers={"X-UDA-User": "proxy.user@example.com", "X-UDA-Groups": "Personal"},
            environ_base={"REMOTE_ADDR": "192.168.1.50"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/auth/login")
        with app.app_context():
            assert User.query.count() == 0
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_alias_maps_uda_identity_to_existing_account():
    app = make_app()
    try:
        with app.app_context():
            user = User(email="gerald@example.com")
            user.set_password("existing-password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        app.config["UDA_USER_ALIASES"] = {"uda@example.com": "gerald@example.com"}
        client = app.test_client()
        response = client.get(
            "/",
            headers={"X-UDA-User": "uda@example.com", "X-UDA-Groups": "Personal"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert response.status_code == 302
        with client.session_transaction() as flask_session:
            assert flask_session["_user_id"] == str(user_id)
        with app.app_context():
            assert User.query.count() == 1
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_forwarded_client_ip_does_not_hide_proxy_socket():
    app = make_app()
    try:
        client = app.test_client()
        response = client.get(
            "/",
            headers={
                "X-UDA-User": "proxy.user@example.com",
                "X-UDA-Groups": "Personal",
                "X-Forwarded-For": "203.0.113.25",
            },
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/home")
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()
