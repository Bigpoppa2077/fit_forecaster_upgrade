"""
Forecast service: the prediction code shared by the Streamlit app (app.py) and the
API the Flutter app talks to (api/server.py).

It knows how to:
  * load the saved models (one ensemble per workout type),
  * build the 13 hints (features) for every half hour of any day, past or future,
  * predict how many people will be there, and
  * look up what really happened on the same weekday in past weeks.
"""

import os
from datetime import date, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

from models import (SplitSpecificModels, EnsembleModel, XGBoostModel,
                    RandomForestModel, LinearRegressionModel)
from realtime_learning import RealTimeLearning, slot_to_time

OPEN_SLOTS = list(range(12, 45))          # 06:00 to 22:00 - the gym's opening hours


def load_models(models_dir: str = "models") -> SplitSpecificModels:
    """Load every saved ensemble in models/<workout>/."""
    split_models = SplitSpecificModels()
    for split_dir in sorted(os.listdir(models_dir)):
        path = os.path.join(models_dir, split_dir)
        if os.path.isdir(path):
            ensemble = EnsembleModel([XGBoostModel(), RandomForestModel(), LinearRegressionModel()])
            ensemble.load_ensemble(path)
            # each saved model remembers which hints (features) it was trained with
            split_models.split_models[split_dir.title()] = {
                'model': ensemble, 'feature_cols': ensemble.feature_cols}
    return split_models


def build_hints(data: pd.DataFrame, split_id: str, day: date) -> pd.DataFrame:
    """
    The 13 hints for every opening-hours slot on `day`.

    If `day` is inside the data we already have, use its exact hints. If it's in the
    future, build them from the most recent days we know: "yesterday" is the latest
    known day, averages use the latest known days, and so on.
    """
    d = data[data['split_id'] == split_id]
    counts = d.pivot_table(index='date', columns='time_slot', values='visitor_count')
    counts = counts.reindex(columns=OPEN_SLOTS).fillna(0)
    day_ts = pd.Timestamp(day)
    dow = day_ts.dayofweek

    if day_ts in counts.index:
        rows = d[d['date'] == day_ts].set_index('time_slot').reindex(OPEN_SLOTS)
        hints = rows[['prev_day_attendance', 'prev_week_attendance', 'rolling_3day_avg',
                      'rolling_7day_avg', 'same_weekday_avg']].fillna(0)
    else:
        known = counts[counts.index < day_ts]
        if known.empty:
            known = counts
        same_dow = known[known.index.dayofweek == dow]
        day_before, week_before = day_ts - timedelta(days=1), day_ts - timedelta(days=7)
        hints = pd.DataFrame({
            'prev_day_attendance': known.loc[day_before] if day_before in known.index else known.iloc[-1],
            'prev_week_attendance': (known.loc[week_before] if week_before in known.index
                                     else same_dow.iloc[-1] if len(same_dow) else known.iloc[-1]),
            'rolling_3day_avg': known.tail(3).mean(),
            'rolling_7day_avg': known.tail(7).mean(),
            'same_weekday_avg': same_dow.mean() if len(same_dow) else known.tail(7).mean(),
        })

    slots = np.array(OPEN_SLOTS)
    hints = hints.reset_index(drop=True)
    hints['time_slot'] = slots
    hints['day_of_week'] = dow
    hints['month'] = day_ts.month
    hints['is_weekend'] = int(dow >= 5)
    hints['hour_sin'] = np.sin(2 * np.pi * slots / 48)
    hints['hour_cos'] = np.cos(2 * np.pi * slots / 48)
    hints['day_sin'] = np.sin(2 * np.pi * dow / 7)
    hints['day_cos'] = np.cos(2 * np.pi * dow / 7)
    return hints


def predict_day(data: pd.DataFrame, models: SplitSpecificModels, split_id: str, day: date) -> pd.Series:
    """Predicted people for each opening-hours slot. Index = slot number."""
    info = models.split_models[split_id]
    hints = build_hints(data, split_id, day)[info['feature_cols']]
    pred = np.clip(info['model'].predict(hints), 0, None)
    return pd.Series(pred, index=OPEN_SLOTS)


def past_same_weekday(data: pd.DataFrame, split_id: str, day: date) -> Dict[int, Dict]:
    """For every slot: the average real count on this weekday in earlier weeks."""
    day_ts = pd.Timestamp(day)
    past = data[(data['split_id'] == split_id) & (data['date'].dt.dayofweek == day_ts.dayofweek)
                & (data['date'] < day_ts) & (data['time_slot'].isin(OPEN_SLOTS))]
    out = {}
    for slot, g in past.groupby('time_slot'):
        out[int(slot)] = {'avg': round(float(g['visitor_count'].mean()), 2), 'weeks': int(len(g))}
    return out


class ForecastService:
    """Data + models in one place, for the API. Call reload() after a retrain."""

    def __init__(self, learner: RealTimeLearning = None, models_dir: str = "models"):
        self.learner = learner or RealTimeLearning(models_dir=models_dir)
        self.models_dir = models_dir
        self.reload()

    def reload(self):
        self.data = self.learner.build_training_data()
        self.models = load_models(self.models_dir)

    @property
    def splits(self) -> List[str]:
        return sorted(self.models.split_models.keys())

    def forecast(self, split_id: str, day: date) -> Dict:
        """Everything a client needs to recommend a time for one workout on one day."""
        if split_id not in self.models.split_models:
            raise KeyError(split_id)
        preds = predict_day(self.data, self.models, split_id, day)
        history = past_same_weekday(self.data, split_id, day)
        return {
            'split': split_id,
            'day': str(day),
            'weekday': pd.Timestamp(day).strftime('%A'),
            'slots': [{'slot': int(s), 'time': slot_to_time(int(s)), 'people': round(float(v), 3),
                       'past_avg': history.get(int(s), {}).get('avg'),
                       'past_weeks': history.get(int(s), {}).get('weeks', 0)}
                      for s, v in preds.items()],
        }
