# Fit Forecaster website

Plain static files, no build step needed to deploy.

```
index.html      the project page (what it is, the two versions, the models, the design)
study.html      how the models work, explained simply (interactive)
app/index.html  the clickable demo of the phone app (a saved week of forecasts)
images/         screenshots, design rounds, og.png (the link preview image)
_source/        the templates these pages are built from (not deployed)
```

## Deploy on Vercel

1. On vercel.com: **Add New → Project**, import the `fit-forecaster` GitHub repo.
2. **Root Directory:** click Edit and choose `website`.
3. **Framework Preset:** Other. Leave the build command and output directory empty.
4. Click **Deploy**.

## After the first deploy: link previews

WhatsApp, LinkedIn and others need the full address of the preview image. Rebuild the pages
with your real address, then push again:

```
SITE_URL=https://your-project.vercel.app python website/_source/build.py        # macOS / Linux
$env:SITE_URL="https://your-project.vercel.app"; python website/_source/build.py  # Windows PowerShell
```

## Changing the pages

Edit the templates in `_source/`, then rebuild:

```
python website/_source/build.py         # index.html and study.html
python website/_source/demo/build.py    # app/index.html
```

`study.html` reads its numbers from `backend/experiments/study_results.json`
(made by `python backend/experiments/study.py`).

## Later: the real Flutter build as the demo

```
cd app
flutter build web --release --base-href /app/
```

Copy everything in `app/build/web/` into `website/app/` (replacing `index.html`), then push.
