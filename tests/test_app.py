import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    assert b"$5220.50" in dashboard.data


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
    assert b"$6200.00" in analytics.data  # racer total cost only
    assert b"$3200.00" in analytics.data  # tanya investment includes part
    assert b"$3000.00" in analytics.data  # gerald investment
    assert b"$1600.00" in analytics.data  # profit
    assert b"$800.00" in analytics.data  # profit share

    sold_only = client.get("/analytics?status=sold")
    assert b"Racer" in sold_only.data
    assert b"Project" not in sold_only.data
