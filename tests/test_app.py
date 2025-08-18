import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, Motorbike, Expense
=======
#from app import app, db, Expense


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


def test_add_and_edit_expense(client):
    # add a motorbike
    resp = client.post('/bikes', data={'name': 'Honda'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Honda' in resp.data

    with app.app_context():
        bike_id = Motorbike.query.filter_by(name='Honda').first().id

    # add an expense for the bike
    resp = client.post(f'/bikes/{bike_id}', data={
        'description': 'Oil Change',
        'category': 'Maintenance',
        'amount': '45.50',
        'user': 'alice',

def test_add_expense(client):
    resp = client.post('/add', data={
        'description': 'Oil Change',
        'category': 'Maintenance',
        'amount': '45.50',

        'date': '2024-01-01'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Oil Change' in resp.data

    assert b'alice' in resp.data

    with app.app_context():
        expense_id = Expense.query.filter_by(description='Oil Change').first().id

    # edit the expense
    resp = client.post(f'/expenses/{expense_id}/edit', data={
        'description': 'Chain',
        'category': 'Maintenance',
        'amount': '30.00',
        'user': 'bob',
        'date': '2024-02-01'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Chain' in resp.data
    assert b'bob' in resp.data
    assert b'Oil Change' not in resp.data
    assert b'45.50' in resp.data

    # Ensure total is calculated
    assert b'Total' in resp.data
