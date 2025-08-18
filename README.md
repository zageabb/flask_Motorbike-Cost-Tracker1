# Motorbike Cost Tracker (Flask)

This project is a Flask web application for tracking motorbike expenses. You can manage multiple bikes, log costs under each one, and attribute expenses to different users.

## Features
- Create motorbikes and record expenses for each.
- Capture who incurred a cost with a user field.
- Edit or delete existing expenses.
- View totals per bike.

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
