# Run from the project root:  python experiments/option_a_steps.py
# Measures each Option A change separately (3 runs each), graded on the same hidden days.
# Note: DataProcessor now has member memory on by default; pass member_memory=False to match Option A exactly.
import sys, logging, numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.metrics import r2_score, mean_absolute_error
logging.disable(logging.CRITICAL); sys.path.insert(0,'src')
from data_processor import DataProcessor
from models import SplitSpecificModels, FEATURE_COLS, ORIGINAL_FEATURE_COLS
fp={d:f'week_data/{d}gym.csv' for d in ['mon','tue','wed','thu','fri','sat','sun']}
# oracle: true expected count per (split, weekday, slot)
dp=DataProcessor(); rows=[]
for i,k in enumerate(fp):
    df=pd.read_csv(fp[k]); df['wd']=i; rows.append(df)
m=pd.concat(rows); m['h']=m.avg_time_check_in.apply(dp.convert_time_to_hours); m['sp']=m.fav_group_lesson.apply(dp.parse_workout_splits)
slots=np.arange(12,45); edges=np.append(slots/2,22.5); exp={}
for r in m.itertuples():
    ps=np.diff(norm.cdf(edges-r.h)); ps[0]=norm.cdf(6.5-r.h); ps[-1]=1-norm.cdf(22-r.h)
    for s in r.sp: exp[(s,r.wd)]=exp.get((s,r.wd),0)+0.85/len(r.sp)*ps
steps=[('S0 now (after update 2)',False,ORIGINAL_FEATURE_COLS,False),
       ('S1 + empty half-hours, true yesterday',True,ORIGINAL_FEATURE_COLS,False),
       ('S2 + same-weekday hint',True,FEATURE_COLS,False),
       ('S3 + model settings',True,FEATURE_COLS,True)]
res=[]
for seed in [1,2,3]:
    np.random.seed(seed); grid=DataProcessor(full_grid=True).process_historical_data(fp)
    np.random.seed(seed); nogrid=DataProcessor(full_grid=False).process_historical_data(fp)
    dates=sorted(grid.date.unique()); cut=dates[int(len(dates)*0.8)]
    for name,g,feats,tuned in steps:
        train=(grid if g else nogrid); train=train[train.date<cut]
        sm=SplitSpecificModels(feature_cols=feats,tuned=tuned)
        for s in sorted(grid.split_id.unique()):
            tr=train[train.split_id==s]; te=grid[(grid.split_id==s)&(grid.date>=cut)]
            mdl=sm.create_split_model(s); mdl.train(tr[feats].fillna(0),tr.visitor_count)
            p=np.clip(mdl.predict(te[feats].fillna(0)),0,None)
            res.append((name,seed,s,r2_score(te.visitor_count,p),mean_absolute_error(te.visitor_count,p)))
    for s in sorted(grid.split_id.unique()):
        te=grid[(grid.split_id==s)&(grid.date>=cut)]
        e=[exp[(s,w)][t-12] for w,t in zip(te.day_of_week,te.time_slot)]
        res.append(('*  best possible',seed,s,r2_score(te.visitor_count,e),mean_absolute_error(te.visitor_count,e)))
R=pd.DataFrame(res,columns=['step','seed','split','r2','mae'])
by=R.groupby(['step','split'])[['r2','mae']].mean().round(3)
print(by.r2.unstack().to_string())
print(R.groupby('step')[['r2','mae']].mean().round(3).to_string())
R.to_csv('outputs/option_a_steps.csv',index=False)
