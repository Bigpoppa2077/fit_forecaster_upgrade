"""
Save a week of forecasts as JSON, bundled inside the Flutter app as demo data.
The app uses it when it can't reach the API (no server running, or offline).

    python api/export_demo.py ../fit_forecaster_app/assets/demo/forecasts.json

Days are stored as offsets (0 = the day of export, 1 = the next day, ...) so the
demo still makes sense whatever day someone opens the app.
"""
import json
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, "src"))
os.chdir(ROOT)
from forecast_service import ForecastService  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "forecasts.json"
service = ForecastService()
today = date.today()
days = []
for offset in range(7):
    day = today + timedelta(days=offset)
    days.append({"offset": offset, "weekday": day.strftime("%A"),
                 "forecasts": {s: service.forecast(s, day)["slots"] for s in service.splits}})
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
with open(out, "w") as f:
    json.dump({"exported": str(today), "splits": service.splits, "days": days}, f, separators=(",", ":"))
print(f"Saved {out} ({os.path.getsize(out) // 1024} KB)")
