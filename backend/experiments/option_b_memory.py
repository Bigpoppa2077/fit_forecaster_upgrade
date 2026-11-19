# Run from the project root:  python experiments/option_b_memory.py
# Compares the Option A models on data without and with member memory (3 runs each), plus the best possible score.
import sys, logging, numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.metrics import r2_score, mean_absolute_error
logging.disable(logging.CRITICAL); sys.path.insert(0,'src')
from data_processor import DataProcessor
from models import SplitSpecificModels, FEATURE_COLS
fp={d:f'week_data/{d}gym.csv' for d in ['mon','tue','wed','thu','fri','sat','sun']}
dp=DataProcessor(); rows=[]
for i,k in enumerate(fp):
    df=pd.read_csv(fp[k]); df['wd']=i; rows.append(df)
m=pd.concat(rows); m['h']=m.avg_time_check_in.apply(dp.convert_time_to_hours); m['sp']=m.fav_group_lesson.apply(dp.parse_workout_splits)
sched=m.groupby('id').wd.apply(set).to_dict()
def showprob(memory):
    out={}
    for i,S in sched.items():
        p={d:0.85 for d in S}
        if memory:
            for _ in range(20):
                for d in sorted(S):
                    prev=(d-1)%7
                    p[d]=0.85 if prev not in S else 0.85*(1-p[prev])+0.70*p[prev]
        for d in S: out[(i,d)]=p[d]
    return out
slots=np.arange(12,45); edges=np.append(slots/2,22.5)
def expected(memory):
    sp=showprob(memory); exp={}
    for r in m.itertuples():
        ps=np.diff(norm.cdf(edges-r.h)); ps[0]=norm.cdf(6.5-r.h); ps[-1]=1-norm.cdf(22-r.h)
        for s in r.sp: exp[(s,r.wd)]=exp.get((s,r.wd),0)+sp[(r.id,r.wd)]/len(r.sp)*ps
    return exp
res=[]
for memory in [False,True]:
    exp=expected(memory)
    for seed in [1,2,3]:
        np.random.seed(seed); grid=DataProcessor(member_memory=memory).process_historical_data(fp)
        dates=sorted(grid.date.unique()); cut=dates[int(len(dates)*0.8)]
        sm=SplitSpecificModels()
        for s in sorted(grid.split_id.unique()):
            d=grid[grid.split_id==s]; tr=d[d.date<cut]; te=d[d.date>=cut]
            mdl=sm.create_split_model(s); mdl.train(tr[FEATURE_COLS],tr.visitor_count)
            p=np.clip(mdl.predict(te[FEATURE_COLS]),0,None)
            e=[exp[(s,w)][t-12] for w,t in zip(te.day_of_week,te.time_slot)]
            res.append((memory,seed,s,r2_score(te.visitor_count,p),mean_absolute_error(te.visitor_count,p),r2_score(te.visitor_count,e),mean_absolute_error(te.visitor_count,e),d.visitor_count.mean()))
R=pd.DataFrame(res,columns=['memory','seed','split','r2','mae','best_r2','best_mae','avg_people'])
print(R.groupby(['memory','split'])[['r2','best_r2']].mean().round(3).unstack(0).to_string())
print(R.groupby('memory')[['r2','mae','best_r2','best_mae','avg_people']].mean().round(3).to_string())
