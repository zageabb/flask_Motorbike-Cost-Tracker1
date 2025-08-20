import os
import sys
from datetime import date

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, Motorbike, Expense


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


def _add_sample_data():
    bike = Motorbike(name='Honda')
    db.session.add(bike)
    db.session.commit()
    exp = Expense(
        motorbike=bike,
        description='Oil Change',
        category='Maintenance',
        amount=45.50,
        user='alice',
        date=date(2024, 1, 1),
    )
    db.session.add(exp)
    db.session.commit()
    return exp.id


def test_api_expenses(client):
    with app.app_context():
        exp_id = _add_sample_data()

    headers = {'X-API-KEY': 'testkey'}

    resp = client.get('/api/expenses', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] == 1
    assert data['items'][0]['description'] == 'Oil Change'

    resp = client.get(f'/api/expenses/{exp_id}', headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['description'] == 'Oil Change'
