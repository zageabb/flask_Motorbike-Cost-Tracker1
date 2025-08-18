import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, db, Expense

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()


def test_add_expense(client):
    resp = client.post('/add', data={
        'description': 'Oil Change',
        'category': 'Maintenance',
        'amount': '45.50',
        'date': '2024-01-01'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Oil Change' in resp.data
    assert b'45.50' in resp.data

    # Ensure total is calculated
    assert b'Total' in resp.data
