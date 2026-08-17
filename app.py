from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

import bcrypt
import os
from flask import Blueprint, Flask, flash, redirect, render_template, request, session, url_for
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

from llm_service import LLMError, ask_assistant, list_models
from settings_store import get_settings, save_settings


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
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SEED_SAMPLE_DATA=os.environ.get("SEED_SAMPLE_DATA", "true").lower() in {"1", "true", "yes"},
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


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect", "danger")
        elif len(new_password) < 12:
            flash("New password must be at least 12 characters", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match", "danger")
        elif current_user.check_password(new_password):
            flash("New password must be different from the current password", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password updated successfully", "success")
            return redirect(url_for("main.landing"))

    return render_template("auth/change_password.html")


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


@main_bp.route("/bikes")
def legacy_bikes_url():
    """Keep the deployment-agent health URL and old bookmarks working."""
    return redirect(url_for("main.motorbikes_list"))


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


def _portfolio_context() -> dict:
    bikes = Motorbike.query.order_by(Motorbike.id).all()
    return {
        "currency": "GBP",
        "motorbikes": [
            {
                "id": bike.id, "name": bike.name, "purchase_price": bike.purchase_price,
                "tanya_contribution": bike.tanya_contribution,
                "gerald_contribution": bike.gerald_contribution, "buyer": bike.buyer,
                "is_sold": bike.is_sold, "sale_price": bike.sale_price,
                "ignore": bike.ignore, "total_cost": bike.total_cost,
                "parts": [
                    {"id": part.id, "description": part.description, "source": part.source,
                     "buyer": part.buyer, "cost": part.cost,
                     "purchased_on": part.purchased_on.isoformat() if part.purchased_on else None}
                    for part in bike.parts
                ],
            }
            for bike in bikes
        ],
    }


def _normalise_actions(actions) -> list[dict]:
    if not isinstance(actions, list):
        return []
    allowed = {"create_motorbike", "add_part", "update_motorbike"}
    return [action for action in actions[:20] if isinstance(action, dict) and action.get("type") in allowed]


@main_bp.route("/assistant", methods=["GET", "POST"])
@login_required
def assistant():
    result = None
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if not query:
            flash("Enter a question or data-creation request", "danger")
        else:
            try:
                result = ask_assistant(query, _portfolio_context(), get_settings())
                result["actions"] = _normalise_actions(result.get("actions"))
                session["assistant_actions"] = result["actions"]
            except LLMError as exc:
                flash(str(exc), "danger")
    return render_template("assistant.html", result=result, query=query)


def _number(action: dict, key: str, default=0.0) -> float:
    value = float(action.get(key, default) if action.get(key) is not None else default)
    if value < 0:
        raise ValueError(f"{key} cannot be negative")
    return value


def _apply_assistant_action(action: dict) -> None:
    action_type = action["type"]
    if action_type == "create_motorbike":
        name = str(action.get("name") or "").strip()
        if not name or Motorbike.query.filter(func.lower(Motorbike.name) == name.lower()).first():
            raise ValueError("Motorbike name is missing or already exists")
        tanya = _number(action, "tanya_contribution")
        gerald = _number(action, "gerald_contribution")
        purchase = _number(action, "purchase_price", tanya + gerald)
        if abs(purchase - tanya - gerald) > 0.01:
            purchase = tanya + gerald
        sold = bool(action.get("is_sold", False))
        sale = action.get("sale_price")
        if sold and sale is None:
            raise ValueError("A sold motorbike requires a sale price")
        db.session.add(Motorbike(name=name, purchase_price=purchase,
            tanya_contribution=tanya, gerald_contribution=gerald,
            buyer=str(action.get("buyer") or "") or None, is_sold=sold,
            sale_price=_number(action, "sale_price") if sale is not None else None,
            ignore=bool(action.get("ignore", False))))
        return
    bike = db.session.get(Motorbike, int(action.get("motorbike_id", 0)))
    if not bike:
        raise ValueError("The referenced motorbike does not exist")
    if action_type == "add_part":
        if bike.is_sold:
            raise ValueError(f"Cannot add equipment to sold motorbike {bike.name}")
        description = str(action.get("description") or "").strip()
        if not description:
            raise ValueError("Equipment description is required")
        purchased_on = date.today()
        if action.get("purchased_on"):
            purchased_on = datetime.strptime(str(action["purchased_on"]), "%Y-%m-%d").date()
        db.session.add(Part(motorbike=bike, description=description,
            source=str(action.get("source") or "").strip() or None,
            buyer=str(action.get("buyer") or "other").lower(),
            cost=_number(action, "cost"), purchased_on=purchased_on))
        return
    for key in ("name", "buyer"):
        if key in action and action[key] is not None:
            setattr(bike, key if key == "name" else "buyer", str(action[key]).strip())
    for source, target in (("purchase_price", "purchase_price"),
                           ("tanya_contribution", "tanya_contribution"),
                           ("gerald_contribution", "gerald_contribution")):
        if source in action:
            setattr(bike, target, _number(action, source))
    if "is_sold" in action:
        bike.is_sold = bool(action["is_sold"])
    if "sale_price" in action:
        bike.sale_price = _number(action, "sale_price") if action["sale_price"] is not None else None
    if "ignore" in action:
        bike.ignore = bool(action["ignore"])
    if bike.is_sold and bike.sale_price is None:
        raise ValueError("A sold motorbike requires a sale price")


@main_bp.post("/assistant/apply")
@login_required
def apply_assistant_actions():
    actions = _normalise_actions(session.pop("assistant_actions", []))
    if not actions:
        flash("There are no pending changes to apply", "danger")
        return redirect(url_for("main.assistant"))
    try:
        for action in actions:
            _apply_assistant_action(action)
        db.session.commit()
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        flash(f"No changes were applied: {exc}", "danger")
        return redirect(url_for("main.assistant"))
    flash(f"Applied {len(actions)} LLM-proposed change(s)", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        save_settings(request.form.to_dict())
        flash("LLM settings saved", "success")
        return redirect(url_for("main.settings"))
    configured = get_settings()
    try:
        models = list_models(configured)
        warning = None
    except LLMError as exc:
        models = [configured["model"]] if configured["model"] else []
        warning = str(exc)
    return render_template("settings.html", settings=configured, models=models, warning=warning)


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
