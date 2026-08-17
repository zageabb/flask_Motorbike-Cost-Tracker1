# Motorbike Cost Tracker (Flask)


This project is a Flask web application for tracking motorbike expenses. You can manage multiple bikes, log costs under each one, and attribute expenses to different users.

## Features
- Full Flask replacement for the original Reflex motorbike portfolio tracker.
- Local Ollama assistant grounded in current portfolio data.
- Review-and-confirm LLM creation of motorbikes, parts, equipment, and updates.
- One-time migration utility for the original Reflex SQLite database.
- Create motorbikes and record expenses for each.
- Capture who incurred a cost with a user field.
- Edit or delete existing expenses.
- View totals per bike.

## Features
- Add expenses with date, description, category and amount.
- View all expenses in a table.
- See the total cost of all recorded expenses.


## Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   flask --app app run
   ```
   The app will be available at http://localhost:5000.

## Testing
Run the unit tests with:
```bash
pytest
```

## Reflex data migration

Run against an empty destination database:
```bash
python migrate_reflex.py /path/to/reflex.db sqlite:////absolute/path/to/motorbike_costs.db
```
