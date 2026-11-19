"""
Fit Forecaster API - the bridge between the Python models and the Flutter app.

Run it from the project folder:
    uvicorn api.server:app --host 0.0.0.0 --port 8000

Then open http://localhost:8000/docs to try every endpoint in the browser.

Endpoints
    GET  /health                  is it running?
    GET  /api/splits              the workout types (body groups)
    GET  /api/forecast            predicted people for every half hour of one day
    POST /api/reports             "I was there and saw N people" (feeds retraining)
    POST /api/plans               "I'm going at 21:00" (kept for records)
    GET  /api/model-info          how accurate the models are on unseen days
"""

import json
import os
import sys
import threading
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, "src"))
os.chdir(ROOT)                          # the models and data paths are relative to the project

from forecast_service import ForecastService, OPEN_SLOTS      # noqa: E402
from realtime_learning import FeedbackCollector               # noqa: E402

app = FastAPI(title="Fit Forecaster API", version="1.0")
# Let the Flutter app (including Flutter web in a browser) call this API
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

service = ForecastService()
collector = FeedbackCollector(service.learner)
lock = threading.Lock()                 # one retrain at a time


class Report(BaseModel):
    day: date
    split: str
    slot: int = Field(ge=0, le=47, description="Half-hour slot: 37 = 18:30")
    count: int = Field(ge=0, le=500)


class Plan(BaseModel):
    day: date
    split: str
    slot: int = Field(ge=0, le=47)
    predicted: float = Field(ge=0)


@app.get("/health")
def health():
    return {"ok": True, "splits": len(service.splits)}


@app.get("/api/splits")
def splits():
    return {"splits": service.splits, "open_slots": [OPEN_SLOTS[0], OPEN_SLOTS[-1]]}


@app.get("/api/forecast")
def forecast(split: str = Query(..., examples=["Legs"]),
             day: date = Query(default_factory=date.today)):
    if day < date.today() - timedelta(days=60) or day > date.today() + timedelta(days=14):
        raise HTTPException(400, "Pick a day between 60 days ago and 14 days from now.")
    try:
        return service.forecast(split, day)
    except KeyError:
        raise HTTPException(404, f"Unknown body group '{split}'. Try one of: {', '.join(service.splits)}")


@app.post("/api/reports")
def report(r: Report):
    try:
        collector.report_attendance(r.day, r.split, r.slot, r.count)
    except ValueError as e:
        raise HTTPException(400, str(e))
    retrained = False
    with lock:
        if service.learner.should_retrain():
            service.learner.retrain()
            retrained = True
        service.reload()                 # new reports feed the hints right away
    learner = service.learner
    return {"saved": True, "retrained": retrained,
            "pending": learner.pending_count(), "retrain_every": learner.retrain_every}


@app.post("/api/plans")
def plan(p: Plan):
    if p.split not in service.splits:
        raise HTTPException(404, f"Unknown body group '{p.split}'.")
    collector.collect_prediction_feedback(p.day, p.split, p.slot, p.predicted)
    return {"saved": True}


@app.get("/api/model-info")
def model_info():
    path = os.path.join("models", "evaluation.json")
    if not os.path.exists(path):
        raise HTTPException(404, "No evaluation yet. Run train_and_test.py first.")
    with open(path) as f:
        return json.load(f)
