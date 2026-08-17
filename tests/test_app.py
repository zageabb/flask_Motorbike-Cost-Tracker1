import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module
from app import Motorbike, Part, User, create_app, db


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SEED_SAMPLE_DATA": False,
        }
    )

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_and_login(client, email="owner@example.com", password="strongpass"):
    response = client.post(
        "/auth/signup",
        data={"email": email, "password": password, "confirm": password},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Open dashboard" in response.data
    return response


def test_protected_routes_require_authentication(client):
    response = client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_dashboard_creation_flow(client, app):
    register_and_login(client)

    create_response = client.post(
        "/dashboard",
        data={
            "form_type": "motorbike",
            "name": "Tracker",
            "purchase_price": "5000",
            "tanya_contribution": "2500",
            "gerald_contribution": "2500",
            "buyer": "Tanya",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert b"Motorbike created" in create_response.data

    with app.app_context():
        bike = Motorbike.query.filter_by(name="Tracker").first()
        assert bike is not None
        assert bike.purchase_price == pytest.approx(5000)

    part_response = client.post(
        "/dashboard",
        data={
            "form_type": "part",
            "motorbike_id": str(bike.id),
            "description": "New tires",
            "source": "Shop",
            "cost": "220.50",
            "buyer": "gerald",
            "purchased_on": "2024-01-15",
        },
        follow_redirects=True,
    )
    assert part_response.status_code == 200
    assert b"Part added" in part_response.data

    dashboard = client.get("/dashboard")
    assert b"Tracker" in dashboard.data
    assert "£5220.50".encode() in dashboard.data


def test_analytics_reflects_profit_and_ignore(client, app):
    register_and_login(client)

    # create sold bike through dashboard update
    client.post(
        "/dashboard",
        data={
            "form_type": "motorbike",
            "name": "Racer",
            "purchase_price": "6000",
            "tanya_contribution": "3000",
            "gerald_contribution": "3000",
            "buyer": "Gerald",
            "is_sold": "on",
            "sale_price": "7800",
        },
        follow_redirects=True,
    )

    with app.app_context():
        racer = Motorbike.query.filter_by(name="Racer").first()
        racer.parts.append(
            Part(description="Brakes", source="Garage", buyer="tanya", cost=200)
        )
        db.session.commit()

    # create ignored bike directly via dashboard form
    client.post(
        "/dashboard",
        data={
            "form_type": "motorbike",
            "name": "Project", 
            "purchase_price": "1000",
            "tanya_contribution": "600",
            "gerald_contribution": "400",
            "ignore": "on",
        },
        follow_redirects=True,
    )

    analytics = client.get("/analytics")
    assert analytics.status_code == 200
    # ensure ignored bike does not affect totals
    assert b"Project" in analytics.data  # still listed but greyed out
    assert "£6200.00".encode() in analytics.data  # racer total cost only
    assert "£3200.00".encode() in analytics.data  # tanya investment includes part
    assert "£3000.00".encode() in analytics.data  # gerald investment
    assert "£1600.00".encode() in analytics.data  # profit
    assert "£800.00".encode() in analytics.data  # profit share

    sold_only = client.get("/analytics?status=sold")
    assert b"Racer" in sold_only.data
    assert b"Project" not in sold_only.data


def test_assistant_proposes_then_applies_equipment(client, app, monkeypatch):
    register_and_login(client)
    with app.app_context():
        bike = Motorbike(name="YBR 125", purchase_price=500, tanya_contribution=250,
                         gerald_contribution=250, buyer="Gerald")
        db.session.add(bike)
        db.session.commit()
        bike_id = bike.id

    monkeypatch.setattr(app_module, "ask_assistant", lambda query, portfolio, settings: {
        "reply": "I can add the battery after confirmation.",
        "actions": [{"type": "add_part", "motorbike_id": bike_id,
                     "description": "Battery", "source": "Amazon",
                     "buyer": "tanya", "cost": 35, "purchased_on": "2026-08-17"}],
    })
    proposal = client.post("/assistant", data={"query": "Add a £35 battery"})
    assert proposal.status_code == 200
    assert b"Proposed data changes" in proposal.data
    with app.app_context():
        assert Part.query.count() == 0

    applied = client.post("/assistant/apply", follow_redirects=True)
    assert b"Applied 1 LLM-proposed change" in applied.data
    with app.app_context():
        part = Part.query.one()
        assert part.description == "Battery"
        assert part.cost == 35


def test_assistant_rolls_back_invalid_batch(client, app):
    register_and_login(client)
    with client.session_transaction() as flask_session:
        flask_session["assistant_actions"] = [
            {"type": "create_motorbike", "name": "Valid", "purchase_price": 0,
             "tanya_contribution": 0, "gerald_contribution": 0},
            {"type": "add_part", "motorbike_id": 999, "description": "Missing bike", "cost": 1},
        ]
    response = client.post("/assistant/apply", follow_redirects=True)
    assert b"No changes were applied" in response.data
    with app.app_context():
        assert Motorbike.query.filter_by(name="Valid").first() is None


def test_settings_screen_uses_configured_model(client, monkeypatch):
    register_and_login(client)
    monkeypatch.setattr(app_module, "list_models", lambda settings: ["llama3.2", "qwen3"])
    response = client.get("/settings")
    assert response.status_code == 200
    assert b"qwen3" in response.data


def test_change_password_requires_current_password_and_updates_login(client):
    register_and_login(client, password="original-password")

    wrong = client.post("/auth/change-password", data={
        "current_password": "wrong-password",
        "new_password": "replacement-password",
        "confirm_password": "replacement-password",
    }, follow_redirects=True)
    assert b"Current password is incorrect" in wrong.data

    changed = client.post("/auth/change-password", data={
        "current_password": "original-password",
        "new_password": "replacement-password",
        "confirm_password": "replacement-password",
    }, follow_redirects=True)
    assert b"Password updated successfully" in changed.data

    client.post("/auth/logout")
    old_login = client.post("/auth/login", data={
        "email": "owner@example.com", "password": "original-password"
    })
    assert b"Invalid credentials" in old_login.data
    new_login = client.post("/auth/login", data={
        "email": "owner@example.com", "password": "replacement-password"
    }, follow_redirects=True)
    assert b"Open dashboard" in new_login.data
