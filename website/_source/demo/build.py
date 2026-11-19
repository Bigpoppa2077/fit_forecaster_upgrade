"""Builds website/app/index.html, the clickable web demo, from demo/template.html.
Run from anywhere:  python website/_source/demo/build.py"""
import base64, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
A = os.path.join(ROOT, 'app', 'assets')
data = json.load(open(f'{A}/demo/forecasts.json'))
# keep only what the page needs (smaller page)
for d in data['days']:
    for k, slots in d['forecasts'].items():
        d['forecasts'][k] = [{'slot': s['slot'], 'people': round(s['people'], 3), 'past_avg': s['past_avg'], 'past_weeks': s['past_weeks']} for s in slots]
uri = lambda p: '"data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode() + '"'
t = open(os.path.join(HERE, 'template.html')).read()
t = (t.replace('/*DATA*/', json.dumps(data, separators=(',', ':')))
      .replace('CHALK_PNG', uri(f'{A}/textures/chalk_dust.png'))
      .replace('GHOST_PNG', uri(f'{A}/textures/marker_ghost.png')))
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="Fit Forecaster: find the quietest time to train at the gym, near the time you want.">\n'
        '<meta name="theme-color" content="#1E2522" media="(prefers-color-scheme: dark)">\n'
        '<meta name="theme-color" content="#FBFBF8" media="(prefers-color-scheme: light)">\n')
title_end = t.index('</title>') + len('</title>')
style_end = t.index('</style>') + len('</style>')
page = head + t[:style_end] + '\n</head>\n<body>\n' + t[style_end:] + '\n</body>\n</html>\n'
open(os.path.join(ROOT, 'website', 'app', 'index.html'), 'w').write(page)
print('website/app/index.html', len(page) // 1024, 'KB')
