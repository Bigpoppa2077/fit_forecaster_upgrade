"""
Study: everything the project website's "How the models work" page reports.
Run from the project root:   python experiments/study.py
Writes experiments/study_results.json.

Same data and models as the app: the simulated month (seed 42), 13 hints per half hour,
one XGBoost + Random Forest + Linear Regression blend per body group, trained on the
earlier 80% of days and tested on the last 20%.
"""
import json, os, sys, logging, warnings
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeRegressor

warnings.filterwarnings("ignore"); logging.disable(logging.CRITICAL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src")); os.chdir(ROOT)
from realtime_learning import RealTimeLearning          # noqa: E402
from models import SplitSpecificModels, FEATURE_COLS     # noqa: E402

OPEN = range(12, 45)
data = RealTimeLearning(feedback_dir="/tmp/ff_study_empty_feedback").build_training_data()
data = data[data["time_slot"].isin(OPEN)].copy()
builder = SplitSpecificModels()
F = builder.feature_cols

def scores(y, p):
    return {"r2": float(r2_score(y, p)), "mae": float(mean_absolute_error(y, p)),
            "rmse": float(np.sqrt(mean_squared_error(y, p)))}

out = {"features": F, "groups": {}, "dataset": {}}
ALL_SAVED, ALL_MOVED = [], []
all_y, all_blend, all_naive = [], [], []
imp_xgb, imp_rf = np.zeros(len(F)), np.zeros(len(F))
coef_rows = []
example_week = None

for split in sorted(data["split_id"].unique()):
    d = data[data["split_id"] == split].sort_values(["date", "time_slot"])
    dates = sorted(d["date"].unique())
    cutoff = dates[int(len(dates) * 0.8)]
    tr, te = d[d["date"] < cutoff], d[d["date"] >= cutoff]
    Xtr, ytr, Xte, yte = tr[F].fillna(0), tr["visitor_count"], te[F].fillna(0), te["visitor_count"]
    ens = builder.create_split_model(split)
    ens.train(Xtr, ytr)
    xgb_m, rf_m, lr_m = ens.models
    p = {"XGBoost": np.clip(xgb_m.predict(Xte), 0, None), "Random Forest": np.clip(rf_m.predict(Xte), 0, None),
         "Linear Regression": np.clip(lr_m.predict(Xte), 0, None)}
    blend = np.clip(ens.predict(Xte), 0, None)
    # baselines: same slot last week; the average for this weekday + slot in the training days
    last_week = te["prev_week_attendance"].fillna(0).values
    table = tr.assign(dow=tr["date"].dt.dayofweek).groupby(["dow", "time_slot"])["visitor_count"].mean()
    lookup = np.array([table.get((dd.dayofweek, s), tr["visitor_count"].mean()) for dd, s in zip(te["date"], te["time_slot"])])
    g = {"train_days": int(tr["date"].nunique()), "test_days": int(te["date"].nunique()),
         "test_rows": int(len(te)), "mean_count": float(yte.mean()),
         "models": {k: scores(yte, v) for k, v in p.items()},
         "blend": scores(yte, blend), "last_week": scores(yte, last_week), "lookup": scores(yte, lookup)}
    err = np.abs(yte.values - blend)
    g["within1"] = float((err <= 1).mean()); g["within2"] = float((err <= 2).mean())
    # did the app's choice (quietest in +-3 slots) land on the truly quietest slot?
    te2 = te.assign(pred=blend)
    hits, extra, saved, moved = [], [], [], []
    for day, dd in te2.groupby("date"):
        dd = dd.set_index("time_slot")
        for pref in range(15, 42):
            near = [s for s in range(pref - 3, pref + 4) if s in dd.index]
            chosen = min(near, key=lambda s: (round(dd.loc[s, "pred"], 1), abs(s - pref)))
            truly = dd.loc[near, "visitor_count"].min()
            hits.append(dd.loc[chosen, "visitor_count"] <= truly + 1)
            extra.append(dd.loc[chosen, "visitor_count"] - truly)
            if dd.loc[pref, "pred"] - dd.loc[chosen, "pred"] < 0.5:
                chosen = pref                      # the app keeps your time for less than half a person
            moved.append(chosen != pref)
            saved.append(dd.loc[pref, "visitor_count"] - dd.loc[chosen, "visitor_count"])
    g["pick_within1_of_quietest"] = float(np.mean(hits)); g["pick_extra_people"] = float(np.mean(extra))
    sv, mv = np.array(saved), np.array(moved)
    g["moved_share"] = float(mv.mean()); g["saved_when_moved"] = float(sv[mv].mean()) if mv.any() else 0.0
    g["moved_and_fewer"] = float((sv[mv] > 0).mean()) if mv.any() else 0.0
    g["moved_and_more"] = float((sv[mv] < 0).mean()) if mv.any() else 0.0
    ALL_SAVED.extend(sv[mv].tolist()); ALL_MOVED.extend(mv.tolist())
    out["groups"][split] = g
    all_y += list(yte); all_blend += list(blend); all_naive += list(last_week)
    # what the models pay attention to
    imp_xgb += xgb_m.model.feature_importances_ / 7
    imp_rf += rf_m.model.feature_importances_ / 7
    # linear regression on standardised hints: how much one "typical change" in each hint moves the count
    sd = Xtr.std().replace(0, 1)
    coef_rows.append(pd.Series(lr_m.model.coef_ * sd.values, index=F))
    if split == "Legs":
        week = te2[te2["date"] < te2["date"].min() + pd.Timedelta(days=3)]
        example_week = [{"date": str(r.date.date()), "slot": int(r.time_slot), "actual": int(r.visitor_count),
                         "pred": round(float(r.pred), 2)} for r in week.itertuples()]
        # a tiny real tree, to show how a split works
        t = DecisionTreeRegressor(max_depth=2, min_samples_leaf=50, random_state=0).fit(Xtr, ytr)
        tr_ = t.tree_
        def node(i):
            if tr_.children_left[i] == -1:
                return {"leaf": True, "value": round(float(tr_.value[i][0][0]), 2), "n": int(tr_.n_node_samples[i])}
            return {"leaf": False, "feature": F[tr_.feature[i]], "threshold": round(float(tr_.threshold[i]), 2),
                    "n": int(tr_.n_node_samples[i]), "value": round(float(tr_.value[i][0][0]), 2),
                    "left": node(tr_.children_left[i]), "right": node(tr_.children_right[i])}
        out["example_tree"] = node(0)
        # one evening row to walk through on the page: the first test Saturday at 19:30
        i = te2[(te2["time_slot"] == 39) & (te2["date"].dt.dayofweek == 5)].index[0]
        out["example_row"] = {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else int(v))
                              for k, v in te2.loc[i, F + ["visitor_count"]].items()}
        out["example_row"]["date"] = str(te2.loc[i, "date"].date())
        out["example_row"]["pred"] = round(float(te2.loc[i, "pred"]), 2)
        # inside each model, for that one evening (for the simple "how it works" walk-through)
        xrow = te2.loc[[i], F].fillna(0)
        n_x = xgb_m.model.n_estimators
        out["example_models"] = {
            "preds": {"xgboost": float(xgb_m.predict(xrow)[0]), "random_forest": float(rf_m.predict(xrow)[0]),
                      "linear": float(lr_m.predict(xrow)[0]), "blend": float(ens.predict(xrow)[0])},
            "rf_trees": [round(float(t.predict(xrow.values)[0]), 2) for t in rf_m.model.estimators_],
            "xgb_steps": [round(float(xgb_m.model.predict(xrow, iteration_range=(0, k))[0]), 3) for k in range(1, n_x + 1)],
            "lr_intercept": round(float(lr_m.model.intercept_), 3),
            "lr_parts": {f: round(float(c * v), 3) for f, c, v in zip(F, lr_m.model.coef_, xrow.values[0])},
        }
        # one hint on its own (the usual crowd for this weekday and time) against the real count:
        # a straight line (Linear Regression's idea) and a 4-step staircase (a decision tree's idea)
        from sklearn.linear_model import LinearRegression
        xs, ys = Xtr[["same_weekday_avg"]], ytr
        line = LinearRegression().fit(xs, ys)
        st = DecisionTreeRegressor(max_depth=2, min_samples_leaf=50, random_state=0).fit(xs, ys)
        cuts = sorted(float(t) for t, f in zip(st.tree_.threshold, st.tree_.feature) if f >= 0)
        edges = [float(xs.values.min())] + cuts + [float(xs.values.max())]
        out["one_hint"] = {
            "points": [[round(float(a), 2), int(b)] for a, b in zip(xs.values[:, 0], ys.values)],
            "line": [round(float(line.intercept_), 3), round(float(line.coef_[0]), 3)],
            "steps": [{"from": round(edges[k], 2), "to": round(edges[k + 1], 2),
                       "value": round(float(st.predict(pd.DataFrame({"same_weekday_avg": [(edges[k] + edges[k + 1]) / 2]}))[0]), 2)}
                      for k in range(len(edges) - 1)],
        }

out["overall"] = {"blend": scores(np.array(all_y), np.array(all_blend)), "last_week": scores(np.array(all_y), np.array(all_naive))}
errs = np.abs(np.array(all_y) - np.array(all_blend))
out["overall"]["within1"] = float((errs <= 1).mean()); out["overall"]["within2"] = float((errs <= 2).mean())
out["overall"]["error_hist"] = [int(((errs >= a) & (errs < a + 1)).sum()) for a in range(0, 8)] + [int((errs >= 8).sum())]
asv = np.array(ALL_SAVED)
out["overall"]["recommend"] = {"cases": len(ALL_MOVED), "moved_share": float(np.mean(ALL_MOVED)), "saved_when_moved": float(asv.mean()),
                               "fewer": float((asv > 0).mean()), "same": float((asv == 0).mean()), "more": float((asv < 0).mean())}
out["importance"] = {"xgboost": dict(zip(F, map(float, imp_xgb))), "random_forest": dict(zip(F, map(float, imp_rf)))}
out["linear_effect"] = pd.concat(coef_rows, axis=1).mean(axis=1).round(3).to_dict()
out["example_week_legs"] = example_week
out["dataset"] = {"rows": int(len(data)), "days": int(data["date"].nunique()), "groups": int(data["split_id"].nunique()),
                  "slots_per_day": len(OPEN), "start": str(data["date"].min().date()), "end": str(data["date"].max().date()),
                  "mean_count": float(data["visitor_count"].mean()), "max_count": int(data["visitor_count"].max()),
                  "zero_share": float((data["visitor_count"] == 0).mean())}
json.dump(out, open(os.path.join(ROOT, "experiments", "study_results.json"), "w"), indent=1)
print(json.dumps(out["dataset"]), json.dumps(out["overall"]["recommend"]), {k: round(v, 3) for k, v in out["overall"]["blend"].items()}, {k: round(v, 3) for k, v in out["overall"]["last_week"].items()}, out["overall"]["within1"], out["overall"]["within2"])
for s, g in out["groups"].items():
    print(s, {m: round(v["r2"], 3) for m, v in g["models"].items()}, "blend", round(g["blend"]["r2"], 3), "mae", round(g["blend"]["mae"], 2),
          "lastweek", round(g["last_week"]["r2"], 3), "lookup", round(g["lookup"]["r2"], 3), "moved", round(g["moved_share"], 2), "saved", round(g["saved_when_moved"], 2), "fewer", round(g["moved_and_fewer"], 2), "more", round(g["moved_and_more"], 2))
print("importance xgb", sorted(out["importance"]["xgboost"].items(), key=lambda x: -x[1])[:6])
print("importance rf", sorted(out["importance"]["random_forest"].items(), key=lambda x: -x[1])[:6])
print("linear", out["linear_effect"])
print("tree", json.dumps(out["example_tree"])[:600])
