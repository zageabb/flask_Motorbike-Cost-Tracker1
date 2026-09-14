# Motorbike Cost Tracker (Flask)


## Ubuntu server deployment

Verified on **14 September 2026** against the listeners, user systemd services,
Docker port mappings and deployment registry on `192.168.1.249`.

| Endpoint | Host TCP port | LAN URL |
|---|---:|---|
| Application | 5067 | http://192.168.1.249:5067/ |

Checkout: `/home/zageabb/flask/flask_Motorbike-Cost-Tracker1`.

These are **user** systemd units. Inspect them with:

```bash
systemctl --user status migrated-flask@flask_Motorbike-Cost-Tracker1.service
systemctl --user cat migrated-flask@flask_Motorbike-Cost-Tracker1.service
```

Local verification URL: `http://127.0.0.1:5067/auth/login`. HTTP 200 was observed during this audit.

Development defaults and container-internal ports elsewhere in this repository
may differ from this host deployment. Use the live ports above when accessing
this Ubuntu server; do not start a second copy on a port already occupied.

[Complete Ubuntu port inventory](https://github.com/zageabb/universal-deployment-agent/blob/main/UBUNTU_PORTS.md).

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
