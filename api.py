from flask import Blueprint, request, jsonify, abort, Response
from sqlalchemy import inspect, asc, desc
from datetime import datetime
import csv
import io

api = Blueprint("api", __name__, url_prefix="/api")

API_KEY = None


def init_api(api_key: str | None = None):
    global API_KEY
    API_KEY = api_key


def _require_api_key():
    if API_KEY is None:
        return
    key = request.headers.get("X-API-KEY") or request.args.get("api_key")
    if key != API_KEY:
        abort(403, description="Invalid API key.")


def _model_to_dict(obj):
    mapper = inspect(obj).mapper
    data = {}
    for col in mapper.columns:
        val = getattr(obj, col.key)
        if hasattr(val, "isoformat"):
            data[col.key] = val.isoformat()
        else:
            data[col.key] = val
    return data


@api.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})


@api.route("/expenses", methods=["GET"])
def get_expenses():
    _require_api_key()
    from app import db, Expense

    q = db.session.query(Expense)

    search = request.args.get("search")
    if search:
        q = q.filter(
            (Expense.description.ilike(f"%{search}%"))
            | (Expense.category.ilike(f"%{search}%"))
        )

    sort = request.args.get("sort", "id")
    order = request.args.get("order", "asc").lower()
    col = getattr(Expense, sort, None)
    if col is None:
        abort(400, description=f"Unsupported sort column: {sort}")
    q = q.order_by(desc(col) if order == "desc" else asc(col))

    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 100)), 1), 1000)
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    data = [_model_to_dict(r) for r in rows]
    return jsonify({"page": page, "page_size": page_size, "total": total, "items": data})


@api.route("/expenses/<int:item_id>", methods=["GET"])
def get_expense(item_id: int):
    _require_api_key()
    from app import db, Expense
    row = db.session.query(Expense).get(item_id)
    if not row:
        abort(404)
    return jsonify(_model_to_dict(row))


@api.route("/expenses.csv", methods=["GET"])
def get_expenses_csv():
    _require_api_key()
    from app import db, Expense

    q = db.session.query(Expense)
    search = request.args.get("search")
    if search:
        q = q.filter(
            (Expense.description.ilike(f"%{search}%"))
            | (Expense.category.ilike(f"%{search}%"))
        )
    q = q.order_by(asc(Expense.id))

    rows = q.all()
    dicts = [_model_to_dict(r) for r in rows]

    if not dicts:
        csv_text = ""
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(dicts[0].keys()))
        writer.writeheader()
        writer.writerows(dicts)
        csv_text = output.getvalue()

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )

