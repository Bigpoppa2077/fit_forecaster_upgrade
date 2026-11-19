"""
Accuracy Ladder for Fit Forecaster
==================================
Run from the project root:   python experiments/accuracy_ladder.py

Each "rung" changes ONE thing and re-measures, so you can see exactly what
each fix/improvement is worth. Read it top to bottom alongside the output.

Rungs
  A  Project as-is, scored the way it currently is (random row split)
  B  Same models + features, scored honestly (train on past days, test on future days)
  C  Fix the data bugs (leaky rolling avg, missing zero-count slots, row-based lags)
  D  Better model setup (Poisson XGBoost, weighted ensemble)
  E  More history (180 simulated days instead of 30)
  *  Oracle: the best score ANY model could get on this simulated data
"""

import os, sys, logging, warnings
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
import xgboost as xgb

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from data_processor import DataProcessor  # noqa: E402

SEED = 42
DP = DataProcessor()
OPEN_SLOTS = range(12, 45)   # simulator clips check-in to 06:00-22:00 -> slots 12..44
TEST_FRAC = 0.2              # last 20% of days are the test set

ORIG_FEATURES = ['time_slot', 'day_of_week', 'month', 'is_weekend',
                 'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
                 'prev_day_attendance', 'prev_week_attendance',
                 'rolling_3day_avg', 'rolling_7day_avg']


# ----------------------------------------------------------------------------
# 1. Data: members + simulated visits
# ----------------------------------------------------------------------------
def load_members():
    """Same loading/cleaning as DataProcessor.process_historical_data (first half)."""
    frames = []
    for d in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
        frames.append(pd.read_csv(os.path.join('week_data', f'{d}gym.csv')))
    m = pd.concat(frames, ignore_index=True)
    m['check_in'] = m['avg_time_check_in'].apply(DP.convert_time_to_hours)
    m['vpw'] = pd.to_numeric(m['visit_per_week'], errors='coerce').fillna(1).astype(float)
    m['splits'] = m['fav_group_lesson'].apply(DP.parse_workout_splits)
    return m[['check_in', 'vpw', 'splits']].reset_index(drop=True)


def simulate_visits(members, days, seed):
    """
    Vectorised equivalent of DataProcessor.generate_realistic_visit_patterns
    (same probabilities/noise, just much faster so we can simulate 180+ days).
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp('2025-01-06')           # a Monday, fixed for reproducibility
    n = len(members)
    base_p = members['vpw'].to_numpy() / 7.0
    base_t = members['check_in'].to_numpy()
    rows = []
    for off in range(days):
        date = start + pd.Timedelta(days=off)
        dow = date.dayofweek
        p = base_p * (1.5 if dow == 1 else 0.8)   # the project's hard-coded Tuesday boost
        visit = rng.random(n) < p
        idx = np.flatnonzero(visit)
        t = np.clip(base_t[idx] + rng.normal(0, 1.0, len(idx)), 6, 22)
        split = [members['splits'].iat[i][rng.integers(len(members['splits'].iat[i]))] for i in idx]
        rows.append(pd.DataFrame({'date': date, 'time_slot': (t * 2).astype(int), 'split_id': split}))
    return pd.concat(rows, ignore_index=True)


# ----------------------------------------------------------------------------
# 2. Features
# ----------------------------------------------------------------------------
def original_features(visits):
    """Exactly the project's create_traffic_features logic (bugs included)."""
    v = visits.rename(columns={'date': 'visit_date'}).copy()
    v['user_id'] = 1
    v['duration_minutes'] = 60.0
    return DP.create_traffic_features(v)


def fixed_features(visits, leaky=False):
    """
    Bug fixes vs the original:
      1. FULL GRID: every (date, slot, split) row exists, zero if nobody came.
         Originally quiet slots were simply missing, so the model never saw a 0.
      2. LAGS BY DATE: prev_day = same slot yesterday, prev_week = same slot 7 days ago.
         Originally shift(1)/shift(7) meant "previous ROW", which skips missing days.
      3. NO LEAKAGE: rolling averages use only PAST days (shift(1) before rolling).
         Originally rolling_3day_avg included today's own count = the answer.
    """
    counts = visits.groupby(['date', 'time_slot', 'split_id']).size().rename('visitor_count')
    dates = pd.date_range(visits['date'].min(), visits['date'].max())
    grid = pd.MultiIndex.from_product([dates, OPEN_SLOTS, sorted(visits['split_id'].unique())],
                                      names=['date', 'time_slot', 'split_id'])
    df = counts.reindex(grid, fill_value=0).reset_index()

    df['day_of_week'] = df['date'].dt.dayofweek
    df['month'] = df['date'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['hour_sin'] = np.sin(2 * np.pi * df['time_slot'] / 48)
    df['hour_cos'] = np.cos(2 * np.pi * df['time_slot'] / 48)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

    df = df.sort_values(['split_id', 'time_slot', 'date'])
    g = df.groupby(['split_id', 'time_slot'])['visitor_count']
    df['prev_day_attendance'] = g.shift(1)
    df['prev_week_attendance'] = g.shift(7)
    lag = 0 if leaky else 1   # leaky=True reproduces the original bug, for comparison only
    df['rolling_3day_avg'] = g.transform(lambda x: x.shift(lag).rolling(3, min_periods=1).mean())
    df['rolling_7day_avg'] = g.transform(lambda x: x.shift(lag).rolling(7, min_periods=1).mean())
    # New: average for this slot on the SAME weekday over past weeks (captures weekly pattern)
    df['same_dow_avg'] = df.groupby(['split_id', 'time_slot', 'day_of_week'])['visitor_count'] \
                           .transform(lambda x: x.shift(1).expanding().mean())
    return df.fillna(0).sort_values(['split_id', 'date', 'time_slot']).reset_index(drop=True)


FIXED_FEATURES = ORIG_FEATURES + ['same_dow_avg']


# ----------------------------------------------------------------------------
# 3. Oracle: the true expected count, computed from the simulator's own rules
# ----------------------------------------------------------------------------
def oracle_expected(members, df):
    """
    Because the data is simulated, we know the TRUE average for every
    (split, weekday, slot). A perfect model would predict exactly this.
    Whatever error remains is pure random noise that nobody can predict.
    """
    rows = []
    for _, m in members.iterrows():
        k = len(m['splits'])
        edges = np.array([s / 2 for s in OPEN_SLOTS] + [22.5])
        cdf = norm.cdf(edges - m['check_in'])
        p_slot = np.diff(cdf)
        p_slot[0] = norm.cdf(6.5 - m['check_in'])          # clip below 6:00 lands in slot 12
        p_slot[-1] = 1 - norm.cdf(22 - m['check_in'])       # clip above 22:00 lands in slot 44
        for s in m['splits']:
            rows.append((s, m['vpw'] / 7 / k, p_slot))
    exp = {}
    for s, pv, ps in rows:
        exp[s] = exp.get(s, 0) + pv * ps
    lookup = {}
    for s, vec in exp.items():
        for dow in range(7):
            mult = 1.5 if dow == 1 else 0.8
            for j, slot in enumerate(OPEN_SLOTS):
                lookup[(s, dow, slot)] = vec[j] * mult
    return np.array([lookup.get((s, d, t), 0) for s, d, t in
                     zip(df['split_id'], df['day_of_week'], df['time_slot'])])
    # note: ignores the tiny effect of capping visit probability at 1


# ----------------------------------------------------------------------------
# 4. Models
# ----------------------------------------------------------------------------
def project_models():
    return {'XGBoost': xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1,
                                        subsample=0.8, colsample_bytree=0.8, random_state=SEED),
            'RandomForest': RandomForestRegressor(n_estimators=100, random_state=SEED, n_jobs=-1),
            'LinearReg': LinearRegression()}


def improved_models():
    return {'XGBoost': xgb.XGBRegressor(objective='count:poisson', n_estimators=400, max_depth=4,
                                        learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                                        min_child_weight=5, random_state=SEED),
            'RandomForest': RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                                  random_state=SEED, n_jobs=-1),
            'LinearReg': LinearRegression()}


def time_split(df):
    days = np.sort(df['date'].unique())
    cut = days[int(len(days) * (1 - TEST_FRAC))]
    return df[df['date'] < cut], df[df['date'] >= cut]


def run(df, features, models_fn, split='time', weights=None):
    """Train one ensemble per workout split, return averaged metrics."""
    res = {k: [] for k in ['XGBoost', 'RandomForest', 'LinearReg', 'Ensemble']}
    for s in sorted(df['split_id'].unique()):
        d = df[df['split_id'] == s]
        if split == 'random':
            tr, te = train_test_split(d, test_size=TEST_FRAC, random_state=SEED)
        else:
            tr, te = time_split(d)
        preds = {}
        for name, m in models_fn().items():
            m.fit(tr[features], tr['visitor_count'])
            preds[name] = np.clip(m.predict(te[features]), 0, None)
            res[name].append((r2_score(te['visitor_count'], preds[name]),
                              mean_absolute_error(te['visitor_count'], preds[name])))
        w = weights or {k: 1 / 3 for k in preds}
        ens = sum(preds[k] * w[k] for k in preds) / sum(w.values())
        res['Ensemble'].append((r2_score(te['visitor_count'], ens),
                                mean_absolute_error(te['visitor_count'], ens)))
    return {k: (np.mean([a for a, _ in v]), np.mean([b for _, b in v])) for k, v in res.items()}


def project_exact_score(df, features):
    """What train_and_test.py does: train on ALL rows, then 'test' on 20% of those same rows."""
    out = []
    for s in sorted(df['split_id'].unique()):
        d = df[df['split_id'] == s]
        preds = []
        _, te = train_test_split(d, test_size=TEST_FRAC, random_state=SEED)
        for m in project_models().values():
            m.fit(d[features], d['visitor_count'])
            preds.append(np.clip(m.predict(te[features]), 0, None))
        ens = np.mean(preds, axis=0)
        out.append((r2_score(te['visitor_count'], ens), mean_absolute_error(te['visitor_count'], ens)))
    return np.mean([a for a, _ in out]), np.mean([b for _, b in out])


def lookup_score(df):
    """Simplest possible 'model': average count for (split, weekday, slot) over training days."""
    out = []
    for s in sorted(df['split_id'].unique()):
        tr, te = time_split(df[df['split_id'] == s])
        table = tr.groupby(['day_of_week', 'time_slot'])['visitor_count'].mean()
        p = te.set_index(['day_of_week', 'time_slot']).index.map(table).to_numpy(dtype=float)
        p = np.nan_to_num(p)
        out.append((r2_score(te['visitor_count'], p), mean_absolute_error(te['visitor_count'], p)))
    return np.mean([a for a, _ in out]), np.mean([b for _, b in out])


def oracle_score(members, df):
    out = []
    for s in sorted(df['split_id'].unique()):
        _, te = time_split(df[df['split_id'] == s])
        e = oracle_expected(members, te)
        out.append((r2_score(te['visitor_count'], e), mean_absolute_error(te['visitor_count'], e)))
    return np.mean([a for a, _ in out]), np.mean([b for _, b in out])


def show(label, r):
    e = r['Ensemble']
    parts = '  '.join(f"{k[:4]} {v[0]:.3f}" for k, v in r.items() if k != 'Ensemble')
    print(f"{label:<46} R²={e[0]:6.3f}  MAE={e[1]:5.2f}   ({parts})")


# ----------------------------------------------------------------------------
if __name__ == '__main__':
    print("Loading members ...")
    members = load_members()
    print(f"{len(members)} member rows\n")
    print(f"{'Rung':<46} {'Ensemble (avg over 7 splits)':<28}  (individual model R²)")
    print('-' * 110)

    v30 = simulate_visits(members, 30, SEED)
    orig30 = original_features(v30)
    r, m = project_exact_score(orig30, ORIG_FEATURES)
    print(f"{'A0 as-is, project scoring (test rows in train)':<46} R²={r:6.3f}  MAE={m:5.2f}")
    show("A  as-is, proper random hold-out", run(orig30, ORIG_FEATURES, project_models, 'random'))
    show("B  as-is, time split (past -> future)", run(orig30, ORIG_FEATURES, project_models))
    print("   (A0-B only contain slots where someone showed up, so not comparable to C onward)")
    print()
    W = {'XGBoost': .45, 'RandomForest': .45, 'LinearReg': .10}
    show("C1 full grid + date lags, leak still ON", run(fixed_features(v30, leaky=True), FIXED_FEATURES, project_models))
    fix30 = fixed_features(v30)
    show("C2 full grid + date lags, leak FIXED", run(fix30, FIXED_FEATURES, project_models))
    show("D  C2 + Poisson XGB / tuned RF / weighted", run(fix30, FIXED_FEATURES, improved_models, weights=W))
    r, m = lookup_score(fix30)
    print(f"{'L  lookup table (avg per weekday+slot)':<46} R²={r:6.3f}  MAE={m:5.2f}")
    r, m = oracle_score(members, fix30)
    print(f"{'*  ORACLE, 30 days (best possible)':<46} R²={r:6.3f}  MAE={m:5.2f}")
    print()

    v180 = simulate_visits(members, 180, SEED)
    fix180 = fixed_features(v180)
    show("E  D + 180 days of history", run(fix180, FIXED_FEATURES, improved_models, weights=W))
    r, m = lookup_score(fix180)
    print(f"{'L  lookup table, 180 days':<46} R²={r:6.3f}  MAE={m:5.2f}")
    r, m = oracle_score(members, fix180)
    print(f"{'*  ORACLE, 180 days (best possible)':<46} R²={r:6.3f}  MAE={m:5.2f}")
