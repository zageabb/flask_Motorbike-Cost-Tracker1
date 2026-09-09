from datetime import timedelta

from app import create_app, db


def _make_app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SEED_SAMPLE_DATA": False,
        }
    )
    return app


def test_auth_session_defaults_to_30_days():
    app = _make_app()
    try:
        assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(days=30)
        assert app.config["REMEMBER_COOKIE_DURATION"] == timedelta(days=30)
        assert app.config["SESSION_REFRESH_EACH_REQUEST"] is True
        assert app.config["REMEMBER_COOKIE_REFRESH_EACH_REQUEST"] is True
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_signup_sets_persistent_session_and_remember_cookie():
    app = _make_app()
    try:
        client = app.test_client()
        response = client.post(
            "/auth/signup",
            data={
                "email": "persistent@example.com",
                "password": "strong-password",
                "confirm": "strong-password",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        cookies = response.headers.getlist("Set-Cookie")
        assert any(cookie.startswith("remember_token=") and "Expires=" in cookie for cookie in cookies)
        assert any(cookie.startswith("session=") and "Expires=" in cookie for cookie in cookies)

        with client.session_transaction() as flask_session:
            assert flask_session.permanent is True
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()
