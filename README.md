# Motorbike Cost Tracker (Flask)

This project is a simple Flask web application for tracking motorbike expenses. Users can record costs such as fuel, maintenance, or other purchases and view a running total.

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
