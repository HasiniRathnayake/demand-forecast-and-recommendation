# Sunrise Supermarket AI Platform

Integrated Streamlit platform for supermarket operations and customer engagement.

## Modules

- Demand Forecasting
- Smart Loyalty & Promotions
- Customer Dashboard
- Smart Inventory Intake
- Short-Shipment Detector
- Waste & Performance Monitor

## Tech Stack

- Python 3.11+
- Streamlit
- PostgreSQL (local via `DATABASE_URL`)
- Supabase (authentication/user records)
- Plotly

## Project Structure

```text
app.py
config/
data/
ml/
pages/
scripts/
services/
tests/
ui/
waste_monitor/
modules/short_shipment_detector/
```

## Setup

### 1. Create and activate virtual environment

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install -r Requirements.txt
```

### 3. Configure environment

Create `.env` in project root:

```env
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<db_name>

SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<supabase_anon_or_service_key>

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=<sender_email>
EMAIL_PASSWORD=<app_password>
EMAIL_FROM=<sender_email>

WEATHER_API_KEY=<openweather_api_key>
```

Notes:
- Loyalty, customer dashboard, and campaign data are read from PostgreSQL via `DATABASE_URL`.
- Authentication and registration use Supabase.
- Keep `.env` strictly in `KEY=VALUE` format (no shell commands in this file).

### 4. Run app

```powershell
streamlit run app.py
```

## Testing

### Run unit tests

```powershell
pytest tests -v
```

### Quick connectivity checks

```powershell
python test_env.py
python test_supabase.py
```

## Loyalty Campaign Scheduling

- Future campaigns are queued in `email_log` with `delivery_status = 'scheduled'`.
- Sending is triggered by the staff action **Process Due Scheduled Emails** in Campaign Builder.
- Email History supports filtering by Sent, Failed, and Scheduled.

## Customer Experience Features

- Customer dashboard shows active (non-expired) promotions.
- Customer settings page allows toggling:
	- `email_notification_enabled`
	- `promotional_emails_allowed`
- Login celebration balloons appear when new promotion alerts are detected.

## Common Troubleshooting

1. Loyalty pages show empty data:
- Verify `DATABASE_URL` points to the expected PostgreSQL database.

2. Customer profile not found:
- Ensure logged-in user has a valid `customer_id` linked to a row in `customers`.

3. Scheduled emails not sending automatically:
- Use **Process Due Scheduled Emails** (manual trigger), or add an external scheduler.

4. Dotenv parsing warnings:
- Remove non-`.env` lines and keep one `KEY=VALUE` per line.

## Team

SLIIT AIML Project  
Group: 2026-Y2-S2-KU-AI-02