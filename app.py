from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

import bcrypt
import os
from flask import Blueprint, Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))


class Motorbike(db.Model):
    __tablename__ = "motorbikes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False, default=0.0)
    tanya_contribution = db.Column(db.Float, nullable=False, default=0.0)
    gerald_contribution = db.Column(db.Float, nullable=False, default=0.0)
    buyer = db.Column(db.String(120))
    is_sold = db.Column(db.Boolean, nullable=False, default=False)
    sale_price = db.Column(db.Float)
    ignore = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    parts = db.relationship(
        "Part",
        backref="motorbike",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Part.purchased_on.desc()",
    )

    @property
    def part_total(self) -> float:
        return sum(part.cost for part in self.parts)

    def part_investment(self, buyer: str) -> float:
        buyer_key = buyer.lower()
        return sum(part.cost for part in self.parts if part.buyer.lower() == buyer_key)

    @property
    def total_cost(self) -> float:
        return self.purchase_price + self.part_total

    @property
    def profit(self) -> float:
        if self.is_sold and self.sale_price is not None:
            return self.sale_price - self.total_cost
        return 0.0


class Part(db.Model):
    __tablename__ = "parts"

    id = db.Column(db.Integer, primary_key=True)
    motorbike_id = db.Column(db.Integer, db.ForeignKey("motorbikes.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(120))
    buyer = db.Column(db.String(50), nullable=False, default="tanya")
    cost = db.Column(db.Float, nullable=False, default=0.0)
    purchased_on = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@dataclass
class PortfolioSummary:
    total_cost: float
    projected_sale: float
    actual_profit: float


@dataclass
class AnalyticsTotals:
    total_cost: float
    tanya_investment: float
    gerald_investment: float
    profit: float
    profit_share: float


def create_app(test_config: Optional[Dict] = None) -> Flask:
    app = Flask(__name__)
    database_uri = os.environ.get("DATABASE_URL", "sqlite:///motorbike_costs.db")
    app.config.from_mapping(
        SECRET_KEY="dev-secret-key",
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SEED_SAMPLE_DATA=True,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        if app.config.get("SEED_SAMPLE_DATA", True):
            seed_data()

    return app


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


def seed_data() -> None:
    if User.query.count():
        return

    admin = User(email="admin@example.com")
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.flush()

    tracker = Motorbike(
        name="Tracker 500",
        purchase_price=4200.0,
        tanya_contribution=2100.0,
        gerald_contribution=2100.0,
        buyer="Tanya",
    )
    tracker.parts.extend(
        [
            Part(description="Fork Upgrade", source="Local Shop", buyer="gerald", cost=450.0),
            Part(description="Seat", source="Online", buyer="tanya", cost=120.0),
        ]
    )

    racer = Motorbike(
        name="Racer 750",
        purchase_price=6800.0,
        tanya_contribution=3400.0,
        gerald_contribution=3400.0,
        buyer="Gerald",
        is_sold=True,
        sale_price=9400.0,
    )
    racer.parts.extend(
        [
            Part(description="Engine Tune", source="Garage", buyer="gerald", cost=600.0),
            Part(description="Fairing Kit", source="Aftermarket", buyer="tanya", cost=350.0),
        ]
    )

    db.session.add_all([tracker, racer])
    db.session.commit()


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required", "danger")
            return render_template("auth/login.html")

        user = User.query.filter(func.lower(User.email) == email).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials", "danger")
            return render_template("auth/login.html")

        login_user(user)
        return redirect(url_for("main.landing"))

    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not email or not password:
            flash("Email and password are required", "danger")
            return render_template("auth/signup.html")

        if password != confirm:
            flash("Passwords do not match", "danger")
            return render_template("auth/signup.html")

        if User.query.filter(func.lower(User.email) == email).first():
            flash("Email already registered", "danger")
            return render_template("auth/signup.html")

        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("main.landing"))

    return render_template("auth/signup.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Signed out successfully", "success")
    return redirect(url_for("auth.login"))


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))
    return redirect(url_for("auth.login"))


@main_bp.route("/home")
@login_required
def landing():
    return render_template("landing.html")


@main_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "motorbike":
            _handle_motorbike_creation()
        elif form_type == "part":
            _handle_part_creation()
        else:
            flash("Unsupported action", "danger")
        return redirect(url_for("main.dashboard"))

    motorbikes = Motorbike.query.order_by(Motorbike.created_at.desc()).all()
    summary = _build_portfolio_summary(motorbikes)
    unsold_bikes = [bike for bike in motorbikes if not bike.is_sold]
    return render_template(
        "dashboard.html",
        motorbikes=motorbikes,
        summary=summary,
        unsold_bikes=unsold_bikes,
    )


def _handle_motorbike_creation() -> None:
    name = request.form.get("name", "").strip()
    buyer = request.form.get("buyer", "").strip()
    sale_price_raw = request.form.get("sale_price", "").strip()
    is_sold = request.form.get("is_sold") == "on"
    ignore = request.form.get("ignore") == "on"

    try:
        purchase_price = max(float(request.form.get("purchase_price", "0")), 0.0)
        tanya_contribution = max(float(request.form.get("tanya_contribution", "0")), 0.0)
        gerald_contribution = max(float(request.form.get("gerald_contribution", "0")), 0.0)
        sale_price = float(sale_price_raw) if sale_price_raw else None
    except ValueError:
        flash("Please provide valid numeric values", "danger")
        return

    if not name:
        flash("Motorbike name is required", "danger")
        return

    if sale_price is not None and sale_price < 0:
        flash("Sale price cannot be negative", "danger")
        return

    if is_sold and sale_price is None:
        flash("Provide a sale price for sold bikes", "danger")
        return

    if Motorbike.query.filter(func.lower(Motorbike.name) == name.lower()).first():
        flash("Motorbike name must be unique", "danger")
        return

    combined_contribution = tanya_contribution + gerald_contribution
    if abs(purchase_price - combined_contribution) > 0.01:
        purchase_price = combined_contribution
        flash("Initial cost adjusted to match partner contributions", "info")

    bike = Motorbike(
        name=name,
        purchase_price=purchase_price,
        tanya_contribution=tanya_contribution,
        gerald_contribution=gerald_contribution,
        buyer=buyer or None,
        is_sold=is_sold,
        sale_price=sale_price,
        ignore=ignore,
    )

    db.session.add(bike)
    db.session.commit()
    flash("Motorbike created", "success")


def _handle_part_creation() -> None:
    try:
        motorbike_id = int(request.form.get("motorbike_id", "0"))
    except ValueError:
        flash("Select a motorbike", "danger")
        return

    motorbike = db.session.get(Motorbike, motorbike_id)
    if not motorbike:
        flash("Motorbike not found", "danger")
        return

    if motorbike.is_sold:
        flash("Cannot add parts to sold motorbikes", "danger")
        return

    description = request.form.get("description", "").strip()
    source = request.form.get("source", "").strip()
    buyer = request.form.get("buyer", "tanya").strip().lower() or "tanya"
    purchased_on_raw = request.form.get("purchased_on", "").strip()

    try:
        cost = max(float(request.form.get("cost", "0")), 0.0)
    except ValueError:
        flash("Cost must be a valid number", "danger")
        return

    if not description:
        flash("Part description is required", "danger")
        return

    purchased_on = None
    if purchased_on_raw:
        try:
            purchased_on = datetime.strptime(purchased_on_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid purchase date", "danger")
            return

    part = Part(
        motorbike=motorbike,
        description=description,
        source=source or None,
        buyer=buyer,
        cost=cost,
        purchased_on=purchased_on or date.today(),
    )

    db.session.add(part)
    db.session.commit()
    flash("Part added", "success")


@main_bp.route("/motorbikes")
@login_required
def motorbikes_list():
    motorbikes = Motorbike.query.order_by(Motorbike.created_at.desc()).all()
    return render_template("motorbikes/list.html", motorbikes=motorbikes)


@main_bp.route("/motorbikes/<int:motorbike_id>", methods=["GET", "POST"])
@login_required
def motorbike_detail(motorbike_id: int):
    motorbike = Motorbike.query.get_or_404(motorbike_id)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "update":
            _update_motorbike(motorbike)
        elif action == "delete":
            db.session.delete(motorbike)
            db.session.commit()
            flash("Motorbike deleted", "success")
            return redirect(url_for("main.motorbikes_list"))
        elif action == "add_part":
            _handle_part_creation_for_motorbike(motorbike)
        else:
            flash("Unsupported action", "danger")
        return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))

    return render_template("motorbikes/detail.html", motorbike=motorbike)


def _update_motorbike(motorbike: Motorbike) -> None:
    name = request.form.get("name", motorbike.name).strip()
    buyer = request.form.get("buyer", "").strip() or None
    sale_price_raw = request.form.get("sale_price", "").strip()
    is_sold = request.form.get("is_sold") == "on"
    ignore = request.form.get("ignore") == "on"

    try:
        purchase_price = max(float(request.form.get("purchase_price", motorbike.purchase_price)), 0.0)
        tanya_contribution = max(
            float(request.form.get("tanya_contribution", motorbike.tanya_contribution)), 0.0
        )
        gerald_contribution = max(
            float(request.form.get("gerald_contribution", motorbike.gerald_contribution)), 0.0
        )
        sale_price = float(sale_price_raw) if sale_price_raw else None
    except ValueError:
        flash("Enter valid numeric values", "danger")
        return

    if sale_price is not None and sale_price < 0:
        flash("Sale price cannot be negative", "danger")
        return

    if is_sold and sale_price is None:
        flash("Provide a sale price for sold bikes", "danger")
        return

    if name.lower() != motorbike.name.lower() and Motorbike.query.filter(
        func.lower(Motorbike.name) == name.lower(), Motorbike.id != motorbike.id
    ).first():
        flash("Motorbike name must be unique", "danger")
        return

    combined_contribution = tanya_contribution + gerald_contribution
    if abs(purchase_price - combined_contribution) > 0.01:
        purchase_price = combined_contribution
        flash("Initial cost adjusted to match partner contributions", "info")

    motorbike.name = name
    motorbike.purchase_price = purchase_price
    motorbike.tanya_contribution = tanya_contribution
    motorbike.gerald_contribution = gerald_contribution
    motorbike.buyer = buyer
    motorbike.is_sold = is_sold
    motorbike.sale_price = sale_price
    motorbike.ignore = ignore

    db.session.commit()
    flash("Motorbike updated", "success")


def _handle_part_creation_for_motorbike(motorbike: Motorbike) -> None:
    if motorbike.is_sold:
        flash("Cannot add parts to sold motorbikes", "danger")
        return

    description = request.form.get("description", "").strip()
    source = request.form.get("source", "").strip()
    buyer = request.form.get("buyer", "tanya").strip().lower() or "tanya"
    purchased_on_raw = request.form.get("purchased_on", "").strip()

    try:
        cost = max(float(request.form.get("cost", "0")), 0.0)
    except ValueError:
        flash("Cost must be a valid number", "danger")
        return

    if not description:
        flash("Part description is required", "danger")
        return

    purchased_on = None
    if purchased_on_raw:
        try:
            purchased_on = datetime.strptime(purchased_on_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid purchase date", "danger")
            return

    part = Part(
        motorbike=motorbike,
        description=description,
        source=source or None,
        buyer=buyer,
        cost=cost,
        purchased_on=purchased_on or date.today(),
    )

    db.session.add(part)
    db.session.commit()
    flash("Part added", "success")


@main_bp.route("/parts/<int:part_id>/update", methods=["POST"])
@login_required
def update_part(part_id: int):
    part = Part.query.get_or_404(part_id)
    motorbike_id = part.motorbike_id

    if part.motorbike.is_sold:
        flash("Cannot modify parts on sold motorbikes", "danger")
        return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))

    description = request.form.get("description", part.description).strip()
    source = request.form.get("source", part.source or "").strip() or None
    buyer = request.form.get("buyer", part.buyer).strip().lower() or part.buyer
    purchased_on_raw = request.form.get("purchased_on", part.purchased_on.isoformat()).strip()

    try:
        cost = max(float(request.form.get("cost", part.cost)), 0.0)
    except ValueError:
        flash("Cost must be a valid number", "danger")
        return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))

    purchased_on = part.purchased_on
    if purchased_on_raw:
        try:
            purchased_on = datetime.strptime(purchased_on_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid purchase date", "danger")
            return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))

    part.description = description
    part.source = source
    part.buyer = buyer
    part.cost = cost
    part.purchased_on = purchased_on

    db.session.commit()
    flash("Part updated", "success")
    return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))


@main_bp.route("/parts/<int:part_id>/delete", methods=["POST"])
@login_required
def delete_part(part_id: int):
    part = Part.query.get_or_404(part_id)
    motorbike_id = part.motorbike_id

    if part.motorbike.is_sold:
        flash("Cannot delete parts from sold motorbikes", "danger")
        return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))

    db.session.delete(part)
    db.session.commit()
    flash("Part removed", "success")
    return redirect(url_for("main.motorbike_detail", motorbike_id=motorbike_id))


@main_bp.route("/analytics")
@login_required
def analytics():
    status_filter = request.args.get("status", "all").lower()
    motorbikes_query = Motorbike.query

    if status_filter == "sold":
        motorbikes_query = motorbikes_query.filter_by(is_sold=True)
    elif status_filter == "unsold":
        motorbikes_query = motorbikes_query.filter_by(is_sold=False)

    motorbikes = motorbikes_query.order_by(Motorbike.created_at.desc()).all()
    analytics_rows = [_build_analytics_row(bike) for bike in motorbikes]
    totals = _build_analytics_totals(analytics_rows)

    return render_template(
        "analytics.html",
        status_filter=status_filter,
        rows=analytics_rows,
        totals=totals,
    )


def _build_portfolio_summary(motorbikes: Iterable[Motorbike]) -> PortfolioSummary:
    relevant = [bike for bike in motorbikes if not bike.ignore]
    total_cost = sum(bike.total_cost for bike in relevant)
    projected_sale = sum(bike.total_cost * 2 for bike in relevant if not bike.is_sold)
    actual_profit = sum(
        (bike.sale_price - bike.total_cost)
        for bike in relevant
        if bike.is_sold and bike.sale_price is not None
    )
    return PortfolioSummary(total_cost=total_cost, projected_sale=projected_sale, actual_profit=actual_profit)


def _build_analytics_row(bike: Motorbike) -> Dict:
    tanya_investment = bike.tanya_contribution + bike.part_investment("tanya")
    gerald_investment = bike.gerald_contribution + bike.part_investment("gerald")
    profit = bike.profit
    profit_share = profit / 2 if profit else 0.0

    return {
        "id": bike.id,
        "name": bike.name,
        "buyer": bike.buyer,
        "purchase_price": bike.purchase_price,
        "total_cost": bike.total_cost,
        "tanya_investment": tanya_investment,
        "gerald_investment": gerald_investment,
        "profit": profit,
        "profit_share": profit_share,
        "is_sold": bike.is_sold,
        "ignore": bike.ignore,
    }


def _build_analytics_totals(rows: List[Dict]) -> AnalyticsTotals:
    relevant = [row for row in rows if not row["ignore"]]
    return AnalyticsTotals(
        total_cost=sum(row["total_cost"] for row in relevant),
        tanya_investment=sum(row["tanya_investment"] for row in relevant),
        gerald_investment=sum(row["gerald_investment"] for row in relevant),
        profit=sum(row["profit"] for row in relevant),
        profit_share=sum(row["profit_share"] for row in relevant),
    )


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
