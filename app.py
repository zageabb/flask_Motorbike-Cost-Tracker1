from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os

from api import api, init_api

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///motorbike_costs.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Enable CORS for API routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register API blueprint and initialize API key
app.register_blueprint(api)
init_api(api_key=os.environ.get("API_KEY", "testkey"))



class Motorbike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    expenses = db.relationship('Expense', backref='motorbike', lazy=True)

    def __repr__(self):
        return f'<Motorbike {self.name}>'


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorbike_id = db.Column(db.Integer, db.ForeignKey('motorbike.id'), nullable=False)
    user = db.Column(db.String(80), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    description = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Expense {self.description}>'


@app.route('/')

def home():
    return redirect(url_for('list_bikes'))


@app.route('/bikes', methods=['GET', 'POST'])
def list_bikes():
    if request.method == 'POST':
        name = request.form['name']
        bike = Motorbike(name=name)
        db.session.add(bike)
        db.session.commit()
        return redirect(url_for('list_bikes'))
    bikes = Motorbike.query.order_by(Motorbike.name).all()
    return render_template('bikes.html', bikes=bikes)


@app.route('/bikes/<int:bike_id>', methods=['GET', 'POST'])
def bike_detail(bike_id):
    bike = Motorbike.query.get_or_404(bike_id)
    if request.method == 'POST':
        description = request.form['description']
        category = request.form['category']
        amount = float(request.form['amount'])
        user = request.form['user']
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
        expense = Expense(motorbike=bike, description=description, category=category, amount=amount, user=user, date=date)
        db.session.add(expense)
        db.session.commit()
        return redirect(url_for('bike_detail', bike_id=bike_id))
    expenses = Expense.query.filter_by(motorbike_id=bike_id).order_by(Expense.date.desc()).all()
    total = sum(e.amount for e in expenses)
    return render_template('expenses.html', bike=bike, expenses=expenses, total=total)


@app.route('/expenses/<int:expense_id>/edit', methods=['GET', 'POST'])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if request.method == 'POST':
        expense.description = request.form['description']
        expense.category = request.form['category']
        expense.amount = float(request.form['amount'])
        expense.user = request.form['user']
        date_str = request.form.get('date')
        expense.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else expense.date
        db.session.commit()
        return redirect(url_for('bike_detail', bike_id=expense.motorbike_id))
    return render_template('edit_expense.html', expense=expense)


@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    bike_id = expense.motorbike_id
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for('bike_detail', bike_id=bike_id))

def index():
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    total = sum(e.amount for e in expenses)
    return render_template('index.html', expenses=expenses, total=total)

@app.route('/add', methods=['POST'])
def add_expense():
    description = request.form['description']
    category = request.form['category']
    amount = float(request.form['amount'])
    date_str = request.form.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
    expense = Expense(description=description, category=category, amount=amount, date=date)
    db.session.add(expense)
    db.session.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5002, debug=True)
