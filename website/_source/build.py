"""Builds website/index.html (the project page) and website/study.html (the models explained simply)
from template.html, study_template.html and backend/experiments/study_results.json.
Run from anywhere:  python website/_source/build.py
Optional: set SITE_URL (e.g. https://fit-forecaster.vercel.app) so link previews get a full image address."""
import base64, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'website')
SITE = os.environ.get('SITE_URL', '').rstrip('/')
A = os.path.join(ROOT, 'app', 'assets', 'textures')
og_img = (SITE + '/' if SITE else '') + 'images/og.png'
og_url = f'<meta property="og:url" content="{SITE}/">\n' if SITE else ''

uri = lambda p: '"data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode() + '"'
t = open(os.path.join(HERE, 'template.html')).read().replace('CHALK_PNG', uri(f'{A}/chalk_dust.png')).replace('GHOST_PNG', uri(f'{A}/marker_ghost.png'))
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="Fit Forecaster finds the quietest time to train at the gym, near the time you want. Python ML models and a Flutter app.">\n'
        '<meta name="author" content="Varshyan Suresh">\n'
        '<meta property="og:title" content="Fit Forecaster">\n'
        '<meta property="og:description" content="Find the quietest time to train, near the time you want.">\n'
        f'<meta property="og:image" content="{og_img}">\n' + og_url + '<meta name="twitter:card" content="summary_large_image">\n')
end = t.index('</style>') + len('</style>')
open(os.path.join(OUT, 'index.html'), 'w').write(head + t[:end] + '\n</head>\n<body>\n' + t[end:] + '\n</body>\n</html>\n')
print('ok', len(t) // 1024, 'KB')

# ---- the study page (a separate full HTML document, also used as-is in the artifact's files)
import json
R = json.load(open(os.path.join(ROOT, 'backend', 'experiments', 'study_results.json')))
G = R['groups']; avg = lambda f: sum(f(g) for g in G.values()) / len(G)
ov, rc, ds, ex = R['overall'], R['overall']['recommend'], R['dataset'], R['example_row']
p = lambda x: f"{round(x * 100)}%"
import datetime
d = datetime.date.fromisoformat(ex['date'])
vals = {
  'DS_ROWS': f"{ds['rows']:,}", 'DS_MEAN': f"{ds['mean_count']:.1f}", 'DS_MAX': str(ds['max_count']), 'DS_ZERO': p(ds['zero_share']),
  'EX_DATE': f"{d.day} {d.strftime('%B')}", 'EX_ACTUAL': str(int(ex['visitor_count'])), 'EX_PRED': f"{ex['pred']:.1f}", 'EX_MISS': f"{abs(ex['pred'] - ex['visitor_count']):.1f}",
  'OV_MAE': f"{ov['blend']['mae']:.1f}", 'OV_W1': p(ov['within1']), 'OV_W2': p(ov['within2']), 'AVG_R2': f"{avg(lambda g: g['blend']['r2']):.2f}",
  'RC_MOVED': p(rc['moved_share']), 'RC_CASES': f"{rc['cases']:,}", 'RC_SAVED': f"{rc['saved_when_moved']:.1f}",
  'RC_FEWER': p(rc['fewer']), 'RC_SAME': p(rc['same']), 'RC_MORE': p(rc['more']),
  'CL_YDAY': str(int(ex['prev_day_attendance'])), 'CL_LWEEK': str(int(ex['prev_week_attendance'])), 'CL_USUAL': f"{ex['same_weekday_avg']:g}",
  'CL_R7': f"{ex['rolling_7day_avg']:.1f}", 'CL_R3': f"{ex['rolling_3day_avg']:.1f}",
}
st = open(os.path.join(HERE, 'study_template.html')).read().replace('CHALK_PNG', uri(f'{A}/chalk_dust.png')).replace('GHOST_PNG', uri(f'{A}/marker_ghost.png'))
st = st.replace('/*STUDY*/', json.dumps(R, separators=(',', ':')))
for k in sorted(vals, key=len, reverse=True): st = st.replace(k, vals[k])
shead = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
         '<meta name="description" content="How Fit Forecaster\'s machine learning models work, how they were tested, and how accurate they are.">\n'
         '<meta property="og:title" content="How Fit Forecaster works">\n' f'<meta property="og:image" content="{og_img}">\n')
e = st.index('</style>') + len('</style>')
open(os.path.join(OUT, 'study.html'), 'w').write(shead + st[:e] + '\n</head>\n<body>\n' + st[e:] + '\n</body>\n</html>\n')
import re; left = re.findall(r'\b(?:DS|EX|OV|RC|AVG|CL)_[A-Z0-9]+\b', st); print('study ok', len(st) // 1024, 'KB', 'leftover:', left)
