from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import date


def migrate(source: str, destination_uri: str) -> tuple[int, int, int]:
    os.environ["DATABASE_URL"] = destination_uri
    os.environ["SEED_SAMPLE_DATA"] = "false"
    from app import Motorbike, Part, User, create_app, db

    app = create_app({"SQLALCHEMY_DATABASE_URI": destination_uri, "SEED_SAMPLE_DATA": False})
    source_db = sqlite3.connect(source)
    source_db.row_factory = sqlite3.Row
    with app.app_context():
        if User.query.count() or Motorbike.query.count() or Part.query.count():
            raise RuntimeError("Destination is not empty; migration stopped without changes.")
        bike_ids: dict[str, int] = {}
        for row in source_db.execute("SELECT * FROM userdb"):
            db.session.add(User(email=row["email"], password_hash=row["password_hash"]))
        for row in source_db.execute("SELECT * FROM motorbikedb"):
            bike = Motorbike(
                name=row["name"], purchase_price=row["initial_cost"] or 0,
                tanya_contribution=row["tanya_initial_cost"] or 0,
                gerald_contribution=row["gerald_initial_cost"] or 0,
                buyer=row["buyer"], is_sold=bool(row["is_sold"]),
                sale_price=row["sold_value"], ignore=bool(row["ignore_from_calculations"]),
            )
            db.session.add(bike)
            db.session.flush()
            bike_ids[row["id"]] = bike.id
        for row in source_db.execute("SELECT * FROM partdb"):
            db.session.add(Part(
                motorbike_id=bike_ids[row["motorbike_id"]], description=row["name"],
                source=row["source"] or None, buyer=(row["buyer"] or "other").lower(),
                cost=row["cost"] or 0, purchased_on=date.today(),
            ))
        db.session.commit()
        counts = (User.query.count(), Motorbike.query.count(), Part.query.count())
    source_db.close()
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate the Reflex tracker database once.")
    parser.add_argument("source")
    parser.add_argument("destination_uri")
    args = parser.parse_args()
    users, bikes, parts = migrate(args.source, args.destination_uri)
    print(f"Migrated {users} users, {bikes} motorbikes, and {parts} parts.")
