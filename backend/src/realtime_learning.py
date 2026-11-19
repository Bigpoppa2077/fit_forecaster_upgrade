"""
Real-time Learning Module for Fit Forecaster

What it does, in plain words:
  1. People report how many were ACTUALLY at the gym ("Chest, 18:00 today, 12 people").
  2. Reports are saved to user_feedback/attendance_reports.csv, so they survive restarts.
  3. When the models are retrained, each real count REPLACES the pretend (simulated) count
     for that half-hour, and the models learn from the result.
  4. Retraining happens automatically after every `retrain_every` new reports, or on demand.

"I'll visit at 21:00" clicks are saved separately (planned_visits.csv). They are plans,
not counts, so they are not used for training.

The old version kept reports in memory, never copied the reported number into the list it
trained from (so every retrain found "no valid data"), and wrote fake member rows into the
week_data CSV files. None of that happens any more: week_data/ is never modified.
"""

import os
import json
import glob
import time
import logging
from datetime import datetime, date
from typing import Dict, Optional

import numpy as np
import pandas as pd

from data_processor import DataProcessor
from models import SplitSpecificModels

logger = logging.getLogger(__name__)

DAY_FILES = ['mongym.csv', 'tuegym.csv', 'wedgym.csv', 'thugym.csv',
             'frigym.csv', 'satgym.csv', 'sungym.csv']
DAY_NAMES = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
KNOWN_SPLITS = ['Arms', 'Back', 'Cardio', 'Chest', 'Core', 'General', 'Legs']
REPORT_COLUMNS = ['report_id', 'reported_at', 'date', 'time_slot', 'split_id',
                  'visitor_count', 'user_id']
PLAN_COLUMNS = ['plan_id', 'created_at', 'date', 'time_slot', 'split_id',
                'predicted_attendance', 'user_id']
SIMULATION_SEED = 42  # same seed as train_and_test.py, so everyone sees the same pretend month


def day_file_paths(data_dir: str) -> Dict[str, str]:
    """The 7 weekday files, keyed by day name."""
    return {name: os.path.join(data_dir, fname) for name, fname in zip(DAY_NAMES, DAY_FILES)
            if os.path.exists(os.path.join(data_dir, fname))}


def slot_to_time(slot: int) -> str:
    return f"{int(slot) // 2:02d}:{(int(slot) % 2) * 30:02d}"


def evaluate_time_split(data: pd.DataFrame, test_size: float = 0.2) -> Dict:
    """
    Honest score: for each workout, train on the earlier 80% of days and test on the
    last 20%, which the model never saw. Returns {workout: {r2, mae, test_samples}}.
    """
    from sklearn.metrics import r2_score, mean_absolute_error
    results = {}
    builder = SplitSpecificModels()
    for split_id in sorted(data['split_id'].unique()):
        d = data[data['split_id'] == split_id]
        dates = sorted(d['date'].unique())
        cutoff = dates[int(len(dates) * (1 - test_size))]
        train, test = d[d['date'] < cutoff], d[d['date'] >= cutoff]
        model = builder.create_split_model(split_id)
        model.train(train[builder.feature_cols].fillna(0), train['visitor_count'])
        pred = np.clip(model.predict(test[builder.feature_cols].fillna(0)), 0, None)
        results[split_id] = {'r2': float(r2_score(test['visitor_count'], pred)),
                             'mae': float(mean_absolute_error(test['visitor_count'], pred)),
                             'test_samples': int(len(test))}
    return results


def write_evaluation(results: Dict, models_dir: str):
    """Save honest scores so the app can show them."""
    with open(os.path.join(models_dir, 'evaluation.json'), 'w') as f:
        json.dump({'evaluated_at': datetime.now().isoformat(),
                   'method': 'trained on earlier days, tested on the last 20% of days',
                   'workouts': results}, f, indent=2)


class RealTimeLearning:
    """Collects attendance reports and retrains the models with them."""

    def __init__(self, data_dir: str = "week_data", models_dir: str = "models",
                 feedback_dir: str = "user_feedback", retrain_every: int = 10):
        self.data_dir = data_dir
        self.models_dir = models_dir
        self.feedback_dir = feedback_dir
        self.retrain_every = retrain_every
        os.makedirs(feedback_dir, exist_ok=True)

        self.reports_file = os.path.join(feedback_dir, 'attendance_reports.csv')
        self.plans_file = os.path.join(feedback_dir, 'planned_visits.csv')
        self.state_file = os.path.join(feedback_dir, 'learning_state.json')

        self._import_old_json_feedback()

    # ------------------------------------------------------------------ storage
    def _read_csv(self, path: str, columns) -> pd.DataFrame:
        if not os.path.exists(path):
            return pd.DataFrame(columns=columns)
        return pd.read_csv(path)

    def _append_row(self, path: str, columns, row: Dict):
        new_file = not os.path.exists(path)
        pd.DataFrame([row], columns=columns).to_csv(path, mode='a', header=new_file, index=False)

    def _read_state(self) -> Dict:
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {'last_retrained_at': None, 'retrain_count': 0, 'last_retrain': None}

    def _write_state(self, state: Dict):
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)

    def _import_old_json_feedback(self):
        """One-time import of old-style feedback JSON files that contain a real count."""
        reports = self.load_reports()
        already = set(reports['report_id'].astype(str))
        for path in sorted(glob.glob(os.path.join(self.feedback_dir, 'feedback_*.json'))):
            try:
                with open(path) as f:
                    fb = json.load(f)
                if fb.get('actual_attendance') is None or fb['feedback_id'] in already:
                    continue
                sel = fb['user_selection']
                self._append_row(self.reports_file, REPORT_COLUMNS, {
                    'report_id': fb['feedback_id'], 'reported_at': fb['timestamp'],
                    'date': str(pd.to_datetime(sel['date']).date()),
                    'time_slot': int(sel['time_slot']), 'split_id': sel['split_id'],
                    'visitor_count': int(fb['actual_attendance']), 'user_id': sel.get('user_id')})
                logger.info(f"Imported old feedback {fb['feedback_id']}")
            except Exception as e:
                logger.warning(f"Could not import {path}: {e}")

    # ------------------------------------------------------------------ reports
    def load_reports(self) -> pd.DataFrame:
        return self._read_csv(self.reports_file, REPORT_COLUMNS)

    def add_report(self, report_date, split_id: str, time_slot: int,
                   visitor_count: int, user_id: Optional[int] = None) -> str:
        """
        Save one real attendance count. Raises ValueError if it doesn't make sense,
        so the app can show the reason instead of saving bad data.
        """
        report_date = pd.to_datetime(report_date).date()
        if report_date > date.today():
            raise ValueError("You can't report a day that hasn't happened yet.")
        if split_id not in KNOWN_SPLITS:
            raise ValueError(f"Unknown workout type '{split_id}'.")
        if not 0 <= int(time_slot) <= 47:
            raise ValueError("Time slot must be between 00:00 and 23:30.")
        if not 0 <= int(visitor_count) <= 500:
            raise ValueError("Attendance must be between 0 and 500 people.")

        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self._append_row(self.reports_file, REPORT_COLUMNS, {
            'report_id': report_id, 'reported_at': datetime.now().isoformat(),
            'date': str(report_date), 'time_slot': int(time_slot), 'split_id': split_id,
            'visitor_count': int(visitor_count), 'user_id': user_id})
        logger.info(f"Saved report {report_id}: {split_id} {report_date} "
                    f"{slot_to_time(time_slot)} = {visitor_count} people")
        return report_id

    def log_planned_visit(self, visit_date, split_id: str, time_slot: int,
                          predicted_attendance: float, user_id: Optional[int] = None) -> str:
        """Save an "I'll visit at ..." click. Kept for records; not used for training."""
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self._append_row(self.plans_file, PLAN_COLUMNS, {
            'plan_id': plan_id, 'created_at': datetime.now().isoformat(),
            'date': str(pd.to_datetime(visit_date).date()), 'time_slot': int(time_slot),
            'split_id': split_id, 'predicted_attendance': round(float(predicted_attendance), 2),
            'user_id': user_id})
        return plan_id

    def pending_count(self) -> int:
        """Reports saved since the last retrain."""
        reports = self.load_reports()
        last = self._read_state().get('last_retrained_at')
        if last is None or reports.empty:
            return len(reports)
        return int((pd.to_datetime(reports['reported_at']) > pd.to_datetime(last)).sum())

    def should_retrain(self) -> bool:
        return self.pending_count() >= self.retrain_every

    # ------------------------------------------------------------------ data + retrain
    def build_training_data(self) -> pd.DataFrame:
        """The pretend month (same seed as train_and_test.py) with real reports applied."""
        processor = DataProcessor()
        # Simulating the month is the slow part, and it doesn't depend on the reports,
        # so do it once per day and reuse it. Applying reports + building hints is fast.
        if getattr(self, '_visits_day', None) != date.today():
            np.random.seed(SIMULATION_SEED)
            self._visits = processor.simulate_visits(day_file_paths(self.data_dir))
            self._visits_day = date.today()
        data = processor.process_historical_data(day_file_paths(self.data_dir),
                                                 real_reports=self.load_reports(),
                                                 visit_patterns=self._visits)
        self.reports_used = processor.reports_used
        return data

    def retrain(self) -> Dict:
        """Rebuild the data with all reports, train fresh models and save them."""
        started = time.time()
        logger.info(f"Retraining with {len(self.load_reports())} saved reports...")
        data = self.build_training_data()

        split_models = SplitSpecificModels()
        split_models.train_split_models(data, target_col='visitor_count')
        for split_id, model_info in split_models.split_models.items():
            model_dir = os.path.join(self.models_dir, split_id.lower())
            model_info['model'].save_ensemble(model_dir)
            with open(os.path.join(model_dir, 'metrics.json'), 'w') as f:
                json.dump(model_info['metrics'], f, indent=2)

        write_evaluation(evaluate_time_split(data), self.models_dir)

        state = self._read_state()
        state['last_retrained_at'] = datetime.now().isoformat()
        state['retrain_count'] = state.get('retrain_count', 0) + 1
        state['last_retrain'] = {
            'reports_saved': len(self.load_reports()),
            'reports_used': self.reports_used,
            'seconds': round(time.time() - started, 1),
            'splits_trained': sorted(split_models.split_models.keys())}
        self._write_state(state)
        logger.info(f"Retraining done: {state['last_retrain']}")
        return state['last_retrain']

    def force_retraining(self) -> Dict:
        """Retrain now, regardless of how many reports are waiting."""
        return self.retrain()

    # ------------------------------------------------------------------ status
    def get_feedback_summary(self) -> Dict:
        reports = self.load_reports()
        state = self._read_state()
        recent = []
        if not reports.empty:
            for _, r in reports.sort_values('reported_at').tail(10).iterrows():
                recent.append({'timestamp': r['reported_at'], 'date': r['date'],
                               'split': r['split_id'], 'time_slot': int(r['time_slot']),
                               'actual_attendance': int(r['visitor_count'])})
        return {
            'total_feedback': len(reports),
            'pending_feedback': self.pending_count(),
            'retrain_every': self.retrain_every,
            'planned_visits': len(self._read_csv(self.plans_file, PLAN_COLUMNS)),
            'last_retrained_at': state.get('last_retrained_at'),
            'last_retrain': state.get('last_retrain'),
            'recent_feedback': recent,
        }


class FeedbackCollector:
    """Small wrapper the Streamlit app uses."""

    def __init__(self, realtime_learner: RealTimeLearning):
        self.learner = realtime_learner

    def collect_prediction_feedback(self, date, split_id, time_slot, predicted_attendance, user_id=None):
        """User clicked "I'll visit at ..." - save the plan."""
        return self.learner.log_planned_visit(date, split_id, time_slot, predicted_attendance, user_id)

    def report_attendance(self, date, split_id, time_slot, actual_attendance, user_id=None):
        """User reported a real count - save it."""
        return self.learner.add_report(date, split_id, time_slot, actual_attendance, user_id)
