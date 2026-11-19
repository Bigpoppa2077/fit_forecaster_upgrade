# Two versions of Fit Forecaster

Fit Forecaster started as a group college project (version 1). Version 2 is a rebuild by V.
The idea stayed the same: tell people the quietest time to train near the time they want.
Almost everything else changed.

This page explains what version 1 had, what was wrong with it, and every change in version 2,
with the reason for each one.

## Version 1: the group project

**What it had**

- A Colab notebook ([`version-1/Fit_Forecaster.ipynb`](version-1/Fit_Forecaster.ipynb)) with a
  deep-learning model (an LSTM) trained on Tuesday data only.
- A Python pipeline that simulated a month of gym visits from the members' weekly timetable.
- XGBoost, Random Forest and Linear Regression, averaged equally, plus Prophet and a neural
  network in the code.
- A Streamlit dashboard with a crowd chart.
- A big plan for what it could become ([`version-1/overhaul_plan.md`](version-1/overhaul_plan.md)).

**What was wrong**

1. **The score was inflated.** It reported R² 0.91, but the models were trained on all the
   rows and then "tested" on some of those same rows. That's like an exam where you've already
   seen the answers.
2. **One clue gave away the answer.** The rolling average for a day included that same day.
3. **The data had holes.** Half hours where nobody came were missing, so the models never saw
   a quiet half hour. "Yesterday" meant the row above, not the real day before.
4. **Learning from users didn't work.** Crowd reports were kept in memory, never used for
   retraining, and fake member rows were written into the original data files.
5. **No clear answer.** The dashboard showed a chart and left the decision to you.

## Version 2: what changed, and why

Each step changed one thing and was measured. The scripts in
[`../backend/experiments`](../backend/experiments) reproduce the numbers.

| # | What changed | Why | Result |
|---|---|---|---|
| 1 | **Honest testing.** Learn from the first 80% of days, get graded on the last 20%, which the models never see while learning. | Version 1 graded the models on rows they had already studied. | R² 0.91 → 0.78: the real starting point |
| 2 | **Fixed the data.** Empty half hours count as 0. "Yesterday" means the real day before. The rolling average stops before the day being guessed. | The models never saw a quiet half hour, and one clue was quietly giving away the answer. | A fair test, with no clue peeking (0.78) |
| 3 | **Better models.** XGBoost uses a Poisson objective (it knows it's counting people), Random Forest got stricter settings, a new clue was added (the usual crowd for that weekday), and the team is weighted 45/45/10. Prophet was removed. | To get as close as possible to the best score any model could reach on that data. | R² 0.80, out of a best possible 0.81 |
| 4 | **A more realistic gym.** Simulated members skip some days, often rest after training, and switch between favourite workouts. | Real people aren't that predictable; a harder, more realistic gym gives a score you can trust. | R² 0.51, off by 1.9 people on average: lower, on purpose |
| 5 | **Learning that works.** Reports are saved to a file, replace the simulated count for that half hour, and the models relearn after every 10 reports. The original data files are never touched. | In version 1, reports were lost and never used, so the app could never get better. | Every real report brings it closer to the real gym |
| 6 | **One clear answer.** Two steps: pick a body group and a time, get the quietest time within 90 minutes and the reason. It keeps your time if moving saves less than half a person. "Pick another time" checks a new one. | At the gym you want an answer, not a chart to read. This took seven design rounds. | When it moves you, you meet about 2.3 fewer people |
| 7 | **A real app, and a website.** A FastAPI server sends forecasts to a Flutter phone app with a chalkboard look. A website and a plain-language explainer show how it works. | So it works on a phone, and anyone can see how it works without reading the code. | See [`../website`](../website) |

Steps 1 to 3 were measured on the first, simpler simulated gym (see
`experiments/accuracy_ladder.py`); step 4 onwards on the more realistic one (`experiments/study.py`).
Scores from the two gyms aren't directly comparable: the realistic gym is harder on purpose.

### The design rounds (step 6)

1. **The original:** a Streamlit dashboard with a chart to read.
2. **Gym poster:** loud and rough, but too much on screen.
3. **One answer:** the best time became the hero.
4. **Two steps:** an iPhone-style wizard with a time wheel.
5. **Street wall:** spray paint, tape labels and a poster.
6. **Volt:** lime and black, a bit too superhero.
7. **Chalkboard (final):** the gym's workout board. The best time is circled, your time is
   crossed out, and every crowd is counted in tally marks.

## What's still limited

- The visits are simulated from a timetable; real check-in data would help the most.
- A month is short: only 4 or 5 of each weekday to learn from.
- Small crowds (2 to 4 people, like Arms and Core) are mostly chance.
- Holidays, weather and exam weeks aren't in the clues.
