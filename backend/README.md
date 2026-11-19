# Fit Forecaster: backend

The Python part of Fit Forecaster: the data, the simulation, the models, the API for the phone app,
and the Streamlit version of the app. See the [main README](../README.md) for the whole project.

Predicts how many people will be at the gym for each workout type (Arms, Back, Cardio,
Chest, Core, General, Legs) in every half hour, and suggests the quietest time to go.

## Run it

```
pip install -r requirements.txt
python train_and_test.py      # trains the models and saves honest test scores (about a minute)
streamlit run app.py          # opens the app in your browser
```

## How it works

1. **Data** – `week_data/` holds 7 files, one per weekday. Together they are a weekly
   timetable of ~5,000 members: being in `mongym.csv` means "goes on Mondays", with their
   usual arrival time and favourite workouts.
2. **Simulated month** – there are no real visit logs, so `src/data_processor.py` simulates
   30 days: on each day, members listed for that weekday show up with an 85% chance
   (70% if they trained the day before), arrive near their usual time, and rotate through
   their favourite workouts.
3. **Counting** – visitors are counted per date, half hour and workout, including half
   hours where nobody came (0).
4. **Hints (features)** – 13 numbers per half hour: time, weekday, yesterday's count,
   last week's count, 3- and 7-day averages, and the average for the same weekday.
   All hints use only earlier days, so the model can't see the answer.
5. **Models** – for each workout, XGBoost + Random Forest + Linear Regression, combined
   with weights 0.45 / 0.45 / 0.10 (`src/models.py`).
6. **Honest testing** – models are trained on the first 80% of days and tested on the last
   20%, which they never saw. Current result: off by about 1.9 people per half hour on
   average, and R² ≈ 0.51 averaged over the body groups.
7. **Recommending a time** – the app looks 90 minutes either side of your preferred time
   and picks the quietest half hour. If it would save less than half a person, it keeps your
   time. The reasons shown (fewer people, how far it moves you, how busy the day is, past weeks)
   all come from the model's predictions and the data.
8. **Learning from real reports** – in the app's sidebar, anyone can report how many
   people were really there. Reports are saved to `user_feedback/attendance_reports.csv`,
   replace the simulated count for that half hour, and the models retrain after every
   10 reports (`src/realtime_learning.py`).

## Files

| File | What it does |
|---|---|
| `app.py` | The Streamlit app: step 1 (body group + preferred time), step 2 (best nearby time + reasons) |
| `components/time_wheel/` | The iPhone-alarm style scroll wheel (plain HTML/JS, no build needed) |
| `.streamlit/config.toml` | Base colours (dark mode, iOS blue) |
| `static/fonts/` | Bundled fonts for the street theme: Rubik Spray Paint (SIL OFL) and Permanent Marker (Apache 2.0), with their licences |
| `train_and_test.py` | Trains, tests (honestly) and saves all models |
| `src/data_processor.py` | Loads the CSVs, simulates visits, builds the hints |
| `src/models.py` | The three models and how they are combined |
| `src/realtime_learning.py` | Attendance reports and retraining |
| `src/forecast_service.py` | Prediction code shared by the Streamlit app and the API |
| `api/server.py` | FastAPI server the Flutter app talks to (`uvicorn api.server:app --port 8000`, docs at `/docs`) |
| `api/export_demo.py` | Saves a week of forecasts as the Flutter app's demo data |
| `src/recommendation_engine.py` | Version 1's quota-based recommender, kept for reference (the app uses the simpler rule above) |
| `manage_realtime_learning.py` | Command-line tools: backup, restore, stats, retrain |
| `experiments/` | Scripts that reproduce each improvement step. `study.py` makes every number on the website's explainer page |

**Flutter app:** the phone app lives in [`../app`](../app). Start the API with `uvicorn api.server:app --host 0.0.0.0 --port 8000`, then follow that folder's README.

**Version 1:** the original group project's notebook and plan are kept in [`../docs/version-1`](../docs/version-1).

**Look:** the app uses the "street" theme by default (spray-paint headings, tape labels, a taped poster for the best time). It has colour sets called looks: `wall` and `voltdark` (dark; `wall` is the default), and the light ones `highlighter`, `volt`, `tangerine`, `grape` and `tomato`. Try one by adding `?look=volt` to the app's address, or run `FF_LOOK=volt streamlit run app.py`. For a light look, also set `base = "light"` in `.streamlit/config.toml` so Streamlit's own pop-ups match. For the plain iOS look, run `FF_THEME=clean streamlit run app.py`.
