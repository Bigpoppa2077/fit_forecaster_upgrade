"""
Fit Forecaster - Streamlit app (iOS-style, two steps)

Step 1  Pick a body group and your preferred time on a scroll wheel.
Step 2  See the best time near what you picked, and why.
"""

import os
import sys
import json
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from models import (SplitSpecificModels, EnsembleModel, XGBoostModel,
                    RandomForestModel, LinearRegressionModel)
from realtime_learning import RealTimeLearning, FeedbackCollector, slot_to_time
import forecast_service as fs

st.set_page_config(page_title="Fit Forecaster", page_icon="🏋️", layout="centered",
                   initial_sidebar_state="collapsed")

# ----------------------------------------------------------------------------- settings
OPEN_SLOTS = list(range(12, 45))          # 06:00 to 22:00 - the gym's opening hours
SEARCH = 3                                # look 3 half-hours (90 min) either side of your time
SAME_ENOUGH = 0.5                         # if a time is less than half a person quieter, keep yours
# Look: "street" = gym-wall theme (spray-paint headings, marker text, taped poster card)
#       "clean"  = the plain iOS dark look. Change it here, or run with FF_THEME=clean.
THEME = os.environ.get("FF_THEME", "street")

# Colour sets for the street theme: "wall" and "voltdark" are dark, the others are light.
# Try one by adding ?look=volt (etc.) to the app's address, or set FF_LOOK.
#   bg/panel/text/muted: page, cards, main text, grey text      accent/on_accent: buttons, chosen pill
#   stroke: paint line under titles                              sticker: hard shadow under buttons
#   paper/paper_ink/paper_muted: the best-time poster            tape/tape_ink: section labels
#   quiet/moderate/busy: crowd dots                              grain: wall texture ("1" light specks, "0" dark)
PALETTES = {
    "ios":         dict(dark=True,  bg="#000000", panel="#141416", text="#FFFFFF", muted="rgba(235,235,245,.62)",
                        accent="#0A84FF", on_accent="#FFFFFF", stroke="#0A84FF", sticker="transparent",
                        paper="#141416", paper_ink="#FFFFFF", paper_muted="rgba(235,235,245,.62)",
                        tape="#1C1C1E", tape_ink="#FFFFFF", quiet="#30D158", moderate="#FFD60A", busy="#FF453A",
                        icon="#8E8E93", chip="#3A3A3C", chip_ink="#FFFFFF", grain="1"),
    "wall":        dict(dark=True,  bg="#0C0C0D", panel="#161618", text="#FFFFFF", muted="rgba(235,235,245,.62)",
                        accent="#0A84FF", on_accent="#FFFFFF", stroke="#0A84FF", sticker="rgba(255,255,255,.85)",
                        paper="#F2EFE8", paper_ink="#121212", paper_muted="#5A5A5A",
                        tape="#E4DCC6", tape_ink="#121212", quiet="#30D158", moderate="#FFD60A", busy="#FF453A",
                        icon="#8E8E93", chip="#3A3A3C", chip_ink="#FFFFFF", grain="1"),
    "highlighter": dict(dark=False, bg="#F4F3EE", panel="#FFFFFF", text="#121212", muted="rgba(18,18,18,.58)",
                        accent="#FF2E88", on_accent="#FFFFFF", stroke="#FF2E88", sticker="#121212",
                        paper="#FFE94A", paper_ink="#121212", paper_muted="rgba(18,18,18,.62)",
                        tape="#151515", tape_ink="#FFFFFF", quiet="#13A150", moderate="#E3A008", busy="#E5372B",
                        icon="#8A8A8A", chip="#121212", chip_ink="#FFFFFF", grain="0"),
    "volt":        dict(dark=False, bg="#ECEDE7", panel="#FFFFFF", text="#0F0F0F", muted="rgba(15,15,15,.58)",
                        accent="#C6F432", on_accent="#0F0F0F", stroke="#FF4F1F", sticker="#0F0F0F",
                        paper="#0F0F0F", paper_ink="#C6F432", paper_muted="rgba(255,255,255,.66)",
                        tape="#C6F432", tape_ink="#0F0F0F", quiet="#13A150", moderate="#E3A008", busy="#E5372B",
                        icon="#8A8A8A", chip="#0F0F0F", chip_ink="#FFFFFF", grain="0"),
    "voltdark":    dict(dark=True,  bg="#0E0F0C", panel="#1A1B17", text="#F2F3EE", muted="rgba(242,243,238,.6)",
                        accent="#C6F432", on_accent="#0F0F0F", stroke="#FF5A26", sticker="#FF5A26",
                        paper="#C6F432", paper_ink="#0F0F0F", paper_muted="rgba(15,15,15,.62)",
                        tape="#FF5A26", tape_ink="#0F0F0F", quiet="#30D158", moderate="#FFD60A", busy="#FF453A",
                        icon="#8A8B85", chip="#F2F3EE", chip_ink="#0F0F0F", grain="1"),
    "tangerine":   dict(dark=False, bg="#FFF4E8", panel="#FFFFFF", text="#1C1309", muted="rgba(28,19,9,.58)",
                        accent="#FF5A1F", on_accent="#FFFFFF", stroke="#2D4BFF", sticker="#1C1309",
                        paper="#2D4BFF", paper_ink="#FFFFFF", paper_muted="rgba(255,255,255,.78)",
                        tape="#FFD08A", tape_ink="#1C1309", quiet="#13A150", moderate="#E3A008", busy="#E5372B",
                        icon="#9A8F84", chip="#1C1309", chip_ink="#FFFFFF", grain="0"),
    "grape":       dict(dark=False, bg="#F1ECFE", panel="#FFFFFF", text="#1B1033", muted="rgba(27,16,51,.6)",
                        accent="#7B2CFF", on_accent="#FFFFFF", stroke="#FF8A00", sticker="#1B1033",
                        paper="#FF8A00", paper_ink="#1B1033", paper_muted="rgba(27,16,51,.7)",
                        tape="#1B1033", tape_ink="#F1ECFE", quiet="#13A150", moderate="#E3A008", busy="#E5372B",
                        icon="#948BA8", chip="#1B1033", chip_ink="#FFFFFF", grain="0"),
    "tomato":      dict(dark=False, bg="#E8F2FF", panel="#FFFFFF", text="#0B1B33", muted="rgba(11,27,51,.58)",
                        accent="#FF4433", on_accent="#FFFFFF", stroke="#FF4433", sticker="#0B1B33",
                        paper="#FFFFFF", paper_ink="#0B1B33", paper_muted="rgba(11,27,51,.6)",
                        tape="#FFD23F", tape_ink="#0B1B33", quiet="#13A150", moderate="#E3A008", busy="#E5372B",
                        icon="#8796AD", chip="#0B1B33", chip_ink="#FFFFFF", grain="0"),
}
LOOK = st.query_params.get("look") or os.environ.get("FF_LOOK", "wall")
if THEME != "street":
    LOOK = "ios"
elif LOOK not in PALETTES or LOOK == "ios":
    LOOK = "wall"
P = PALETTES[LOOK]
BLUE, GREEN, YELLOW, RED, GREY = P["accent"], P["quiet"], P["moderate"], P["busy"], P["icon"]
CROWD_COLORS = {"Quiet": GREEN, "Moderate": YELLOW, "Busy": RED}
TEXT, MUTED = P["text"], P["muted"]

# The scroll-wheel time picker (components/time_wheel/index.html)
_time_wheel = components.declare_component(
    "time_wheel", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "time_wheel"))

def time_wheel(value: int, key: str) -> int:
    """iPhone-alarm style picker. Returns the chosen half-hour slot (e.g. 37 = 18:30)."""
    current = st.session_state.get(key)            # the wheel's latest value, if it has one
    start = int(current) if current is not None else int(value)
    out = _time_wheel(value=start, min_slot=OPEN_SLOTS[0], max_slot=OPEN_SLOTS[-1],
                      theme=THEME, colors=WHEEL_COLORS, key=key, default=start)
    return int(out) if out is not None else int(value)

st.markdown("""
<style>
/* ---------- iOS-style dark mode, matte finish, iOS blue kept ----------
   Flat soft-grey capsules and panels with a faint hairline edge. No shine, no glow.
   (For more of a glass look: give --lg-fill some transparency, add a blur to
   --lg-blur and a brighter edge to --lg-rim.) */
:root {
  --text:#FFFFFF; --muted:rgba(235,235,245,.62); --blue:#0A84FF; --sep:rgba(255,255,255,.10);
  /* Matte finish: flat soft fills, a faint hairline edge, no shine, no glow */
  --lg-fill: #1C1C1E;
  --lg-blur: none;
  --lg-rim: inset 0 0 0 .5px rgba(255,255,255,.08);
  --lg-shadow: 0 0 0 transparent;
  --lg-blue: #0A84FF;
  --lg-blue-shadow: 0 0 0 transparent;
  --panel-fill: #141416;
  --panel-blur: none;
  --panel-rim: inset 0 0 0 .5px rgba(255,255,255,.07);
}

/* Plain black background: no coloured light, no glow */
.stApp {background: #000000;}
[data-testid="stHeader"] {background: transparent;}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
.block-container {max-width: 440px; padding: 1.2rem 1rem 3rem;}
.stApp, .stApp p, .stApp label, .stApp li, .stMarkdown, button, input, [data-testid="stWidgetLabel"] p {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;}

/* ---------- Panels (hero card, lists, folded sections, dropdown) ---------- */
.ios-list, .ios-hero, [data-testid="stExpander"] details, [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [role="group"] {
  background: var(--panel-fill) !important; border: none !important;
  backdrop-filter: var(--panel-blur); -webkit-backdrop-filter: var(--panel-blur);
  box-shadow: var(--panel-rim) !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div * {background: transparent !important;}
[data-testid="stSelectbox"] [role="group"], [data-baseweb="select"] > div {border-radius: 999px !important; padding-left: 6px;}
[data-testid="stExpander"] details {border-radius: 22px !important;}

/* Step indicator + large title */
.ios-steps {display: flex; gap: 6px; margin: .2rem 0 .9rem;}
.ios-steps i {flex: 1; height: 5px; border-radius: 3px; background: rgba(255,255,255,.14);}
.ios-steps i.on {background: var(--blue);}
.ios-step-label {font-size: .82rem; color: var(--muted); font-weight: 600; letter-spacing: .02em;}
.ios-title {font-size: 2.15rem; font-weight: 800; letter-spacing: -.025em; color: var(--text); margin: .1rem 0 .3rem; line-height: 1.05;}
.ios-subtitle {font-size: 1rem; color: var(--muted); margin-bottom: 1rem;}

/* Grouped-list headers + footers */
.ios-h {font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted);
  margin: 1.5rem 0 .5rem .9rem; font-weight: 600;}
.ios-foot {font-size: .8rem; color: var(--muted); margin: .45rem .9rem 0;}

/* Grouped list */
.ios-list {border-radius: 22px !important; overflow: hidden;}
.ios-row {display: flex; align-items: center; gap: 12px; padding: 11px 16px; position: relative;}
.ios-row + .ios-row::before {content: ""; position: absolute; top: 0; right: 0; left: 58px; height: .5px; background: var(--sep);}
.ios-list.plain .ios-row + .ios-row::before {left: 16px;}
.ios-icon {width: 30px; height: 30px; border-radius: 9px; flex: none; display: grid; place-items: center;
  color: #fff; font-size: 16px; font-weight: 700;}
.ios-row .txt {flex: 1; min-width: 0;}
.ios-row .t1 {font-size: 1rem; color: var(--text); font-weight: 600; letter-spacing: -.005em;}
.ios-row .t2 {font-size: .86rem; color: var(--muted); margin-top: 2px;}
.ios-row .time {font-size: 1.05rem; font-weight: 700; color: var(--text); width: 66px; font-variant-numeric: tabular-nums;}
.ios-row .ppl {flex: 1; color: var(--muted); font-size: .95rem;}
.ios-dot {width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none;}
.ios-badge {font-size: .74rem; font-weight: 700; padding: 3px 9px; border-radius: 999px; flex: none;}
.ios-row.hl {background: rgba(10,132,255,.16);}

/* Result hero */
.ios-hero {border-radius: 30px !important; padding: 18px 20px 22px; margin: .4rem 0 .2rem; text-align: center;}
.ios-hero .k {font-size: .9rem; color: var(--muted); font-weight: 600;}
.ios-hero .v {font-size: clamp(3.8rem, 19vw, 5rem); font-weight: 800; letter-spacing: -.03em; line-height: 1.05; margin: .15rem 0 .35rem;
  color: var(--text); font-variant-numeric: tabular-nums;}
.ios-hero .s {display: inline-flex; align-items: center; gap: 7px; font-size: 1.05rem; font-weight: 700; color: var(--text);}
.ios-hero .p {font-size: .86rem; color: var(--muted); margin-top: .35rem;}

/* ---------- Liquid glass controls ---------- */
.stButton > button, .stFormSubmitButton > button, button[data-variant="pills"] {
  background: var(--lg-fill) !important; border: none !important; color: var(--text) !important;
  backdrop-filter: var(--lg-blur); -webkit-backdrop-filter: var(--lg-blur);
  box-shadow: var(--lg-rim), var(--lg-shadow) !important;
  border-radius: 999px !important; min-height: 50px;
  transition: transform .18s cubic-bezier(.3,.7,.4,1.4), filter .2s ease, background .2s ease;}
.stButton > button:hover, .stFormSubmitButton > button:hover, button[data-variant="pills"]:hover {filter: brightness(1.15);}
.stButton > button:active, .stFormSubmitButton > button:active, button[data-variant="pills"]:active {transform: scale(.95);}

/* body-group capsules */
button[data-variant="pills"] {min-height: 46px; min-width: calc(33.33% - 6px); flex: 1 1 calc(33.33% - 6px);}
button[data-variant="pills"] p {font-size: .98rem !important; font-weight: 600 !important;}

/* prominent glass: Next / I'm going / Log it, and the chosen body group */
.stButton > button[data-testid="stBaseButton-primary"],
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"],
button[data-variant="pills"][aria-checked="true"] {
  background: var(--lg-blue) !important; box-shadow: var(--lg-rim), var(--lg-blue-shadow) !important;}
.stButton > button[data-testid="stBaseButton-primary"],
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] {min-height: 54px;}
.stButton > button[data-testid="stBaseButton-primary"] p,
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] p {
  font-size: 1.08rem !important; font-weight: 700 !important; color: #fff !important;}

/* Back: small clear glass capsule */
.stButton > button[data-testid="stBaseButton-tertiary"] {min-height: 38px !important; padding: 4px 16px 4px 12px !important;}
.stButton > button[data-testid="stBaseButton-tertiary"] p {font-size: .98rem !important; color: var(--text) !important; font-weight: 600 !important;}

[data-testid="stForm"] {border: none !important; padding: 0 !important;}
[data-testid="stWidgetLabel"] p {font-size: .8rem; color: var(--muted);}
/* other buttons (secondary) */
.stButton > button p {font-weight: 600 !important;}
[data-testid="stExpander"] summary p {font-weight: 500 !important;}

/* "Reduce Transparency" on: solid surfaces instead of glass */
@media (prefers-reduced-transparency: reduce) {
  .ios-list, .ios-hero, [data-testid="stExpander"] details, [data-testid="stSelectbox"] [role="group"],
  .stButton > button, button[data-variant="pills"] {
    background: #1C1C1E !important; backdrop-filter: none !important; -webkit-backdrop-filter: none !important;}
}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- street theme
# Gym-wall look: textured wall, spray-paint headings, tape labels, a poster for the best time,
# marker-pen numbers and sticker buttons. Colours come from the palette P (see PALETTES above).
# Fonts are bundled in static/fonts: Rubik Spray Paint (SIL OFL) and Permanent Marker (Apache 2.0).
def _svg(svg: str) -> str:
    return 'url("data:image/svg+xml,' + svg.replace('<', '%3C').replace('>', '%3E').replace('#', '%23').replace('"', "'") + '")'

GRAIN = _svg('<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180"><filter id="n">'
             '<feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="3" stitchTiles="stitch"/>'
             f'<feColorMatrix values="0 0 0 0 {P["grain"]} 0 0 0 0 {P["grain"]} 0 0 0 0 {P["grain"]} 0 0 0 .06 0"/></filter>'
             '<rect width="100%" height="100%" filter="url(#n)"/></svg>').replace('100%', '100%25')
STROKE = _svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 16"><path d="M3 10 C 40 4, 78 13, 118 7 S 186 4, 216 9" '
              f'fill="none" stroke="{P["stroke"]}" stroke-width="5" stroke-linecap="round"/></svg>')
# The time wheel lives in its own frame, so it gets its colours passed in
WHEEL_COLORS = dict(panel=P["panel"], text=P["text"], dim=P["muted"], band=P["accent"] + "55",
                    line=("rgba(255,255,255,.16)" if P["dark"] else "rgba(0,0,0,.14)"))

if THEME == "street":
    line = "rgba(255,255,255,.16)" if P["dark"] else "rgba(0,0,0,.16)"
    outline = "rgba(255,255,255,.5)" if P["dark"] else P["text"]
    sep = "rgba(255,255,255,.10)" if P["dark"] else "rgba(0,0,0,.08)"
    track = "rgba(255,255,255,.14)" if P["dark"] else "rgba(0,0,0,.12)"
    st.markdown(f"""
<style>
@font-face {{font-family: 'Spray'; src: url('app/static/fonts/rubik-spray-paint.woff2') format('woff2'); font-display: swap;}}
@font-face {{font-family: 'Marker'; src: url('app/static/fonts/permanent-marker.woff2') format('woff2'); font-display: swap;}}
:root {{
  --bg: {P["bg"]}; --panel: {P["panel"]}; --text: {P["text"]}; --muted: {P["muted"]};
  --accent: {P["accent"]}; --on-accent: {P["on_accent"]}; --sticker: {P["sticker"]};
  --paper: {P["paper"]}; --paper-ink: {P["paper_ink"]}; --paper-muted: {P["paper_muted"]};
  --tape: {P["tape"]}; --tape-ink: {P["tape_ink"]};
  --line: {line}; --outline: {outline}; --sep: {sep}; --track: {track};
  --blue: {P["accent"]}; --lg-blue: {P["accent"]};
  --hand: 255px 18px 225px 18px / 18px 225px 18px 255px;          /* wobbly, hand-drawn corners */
  --hand-sm: 24px 9px 28px 11px / 11px 26px 9px 24px;
  --marker: 'Marker', 'Comic Sans MS', -apple-system, sans-serif;
  --spray: 'Spray', 'Marker', -apple-system, sans-serif;
}}
.stApp {{background-color: var(--bg); background-image: {GRAIN}; color: var(--text);}}
.stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stMarkdownContainer"] li {{color: var(--text);}}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stWidgetLabel"] p {{color: var(--muted) !important;}}

/* headings: short, wide spray paint, with a paint stroke under the big title */
.ios-title {{font-family: var(--spray); font-weight: 400; font-size: 2.45rem; letter-spacing: 0; line-height: 1.1;
  margin-top: .2rem; color: var(--text);}}
.ios-title::after {{content: ""; display: block; width: 10.5rem; height: 15px; margin-top: .15rem;
  background: {STROKE} no-repeat left center / contain;}}
.ios-step-label {{font-family: var(--marker); font-weight: 400; letter-spacing: .04em; color: var(--muted);}}
.ios-steps i {{height: 6px; border-radius: var(--hand); background: var(--track);}}
.ios-steps i.on {{background: var(--accent);}}
.ios-steps i:first-child {{transform: rotate(-.7deg);}} .ios-steps i:last-child {{transform: rotate(.6deg);}}

/* section labels: strips of tape */
.ios-h {{display: inline-block; font-family: var(--marker); font-weight: 400; font-size: .86rem; letter-spacing: .05em;
  color: var(--tape-ink); background: var(--tape); padding: 4px 13px 2px; margin: 1.7rem 0 .7rem .1rem; transform: rotate(-1.6deg);
  clip-path: polygon(0 10%, 5% 0, 50% 6%, 95% 0, 100% 12%, 98% 55%, 100% 92%, 94% 100%, 50% 94%, 4% 100%, 0 90%, 2% 50%);}}

/* best time: a poster taped to the wall */
.stApp .ios-hero {{background: var(--paper) !important; box-shadow: none !important; border-radius: 5px 3px 6px 4px !important;
  color: var(--paper-ink); transform: rotate(-1.2deg); position: relative; margin: 1.4rem .35rem .8rem; padding: 24px 18px 22px;}}
.ios-hero::before, .ios-hero::after {{content: ""; position: absolute; top: -12px; width: 82px; height: 25px;
  background: var(--tape); opacity: .82;}}
.ios-hero::before {{left: 14px; transform: rotate(-9deg);}} .ios-hero::after {{right: 14px; transform: rotate(8deg);}}
.ios-hero .k {{font-family: var(--marker); font-weight: 400; font-size: 1.02rem; color: var(--paper-muted);}}
.ios-hero .v {{font-family: var(--marker); font-weight: 400; color: var(--paper-ink); font-size: clamp(4.4rem, 23vw, 5.7rem);
  letter-spacing: .01em; line-height: 1.12; margin: .1rem 0 .2rem;}}
.ios-hero .s {{color: var(--paper-ink); font-weight: 700;}}
.ios-hero .p {{color: var(--paper-muted);}}

/* lists, dropdown and folded sections: panels with a hand-drawn edge */
.stApp .ios-list, .stApp [data-testid="stExpander"] details, .stApp [data-testid="stSelectbox"] [role="group"],
.stApp [data-baseweb="select"] > div {{background: var(--panel) !important; box-shadow: inset 0 0 0 1.5px var(--line) !important;
  border-radius: var(--hand-sm) !important;}}
.stApp [data-baseweb="select"] div, .stApp [data-testid="stSelectbox"] [role="group"] * {{color: var(--text) !important;}}
.stApp [data-testid="stExpander"] summary, .stApp [data-testid="stExpander"] summary * {{color: var(--text) !important;}}
.ios-row .t1, .ios-row .time {{color: var(--text);}}
.ios-row .t2, .ios-row .ppl, .ios-foot, .ios-subtitle {{color: var(--muted);}}
.ios-row .time {{font-family: var(--marker); font-weight: 400; font-size: 1.15rem; letter-spacing: .02em;}}
.ios-row.hl {{background: linear-gradient(100deg, transparent 1%, {P["accent"]}55 3%, {P["accent"]}40 93%, transparent 97%);}}
.ios-icon {{border-radius: 50% 44% 54% 46% / 46% 54% 44% 50%;}}
.ios-badge {{font-family: var(--marker); font-weight: 400 !important; font-size: .8rem; transform: rotate(-4deg); border-radius: 4px 7px 3px 6px;}}

/* buttons and body-group pills: marker text, hand-drawn outline; chosen ones are stickers */
.stApp .stButton > button, .stApp .stFormSubmitButton > button, .stApp button[data-variant="pills"] {{
  background: transparent !important; border-radius: var(--hand) !important; box-shadow: inset 0 0 0 2px var(--outline) !important;
  transition: transform .12s ease, box-shadow .12s ease;}}
.stApp .stButton > button p, .stApp .stFormSubmitButton > button p, .stApp button[data-variant="pills"] p,
.stApp [data-testid="stExpander"] summary p {{font-family: var(--marker) !important; font-weight: 400 !important;
  letter-spacing: .02em; color: var(--text) !important;}}
.stApp button[data-variant="pills"] p {{font-size: 1.04rem !important;}}
.stApp .stButton > button[data-testid="stBaseButton-primary"],
.stApp .stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"],
.stApp button[data-variant="pills"][aria-checked="true"] {{
  background: var(--accent) !important; box-shadow: 3px 4px 0 0 var(--sticker) !important;}}
.stApp .stButton > button[data-testid="stBaseButton-primary"] p,
.stApp .stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] p,
.stApp button[data-variant="pills"][aria-checked="true"] p {{color: var(--on-accent) !important;}}
.stApp .stButton > button[data-testid="stBaseButton-primary"] p,
.stApp .stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] p {{font-size: 1.4rem !important;}}
.stApp .stButton > button:active, .stApp .stFormSubmitButton > button:active, .stApp button[data-variant="pills"]:active {{
  transform: translate(2px, 3px) !important; box-shadow: 1px 1px 0 0 var(--sticker) !important;}}
.stApp .stButton > button[data-testid="stBaseButton-tertiary"] {{box-shadow: none !important;}}
.stApp .stButton > button[data-testid="stBaseButton-tertiary"] p {{font-size: 1.05rem !important;}}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- loading
@st.cache_resource
def get_learner():
    return RealTimeLearning()

learner = get_learner()
collector = FeedbackCollector(learner)

@st.cache_data
def load_processed_data():
    # Same pretend month as training (fixed seed), with real attendance reports applied
    return learner.build_training_data()

@st.cache_resource
def load_models():
    return fs.load_models("models")

def load_evaluation():
    path = os.path.join("models", "evaluation.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def retrain_and_reload(reason):
    """Retrain with all saved reports, then reload data + models and redraw the page."""
    with st.spinner("Retraining the models with the reports... (about 15 seconds)"):
        result = learner.retrain()
    load_processed_data.clear()
    load_models.clear()
    st.session_state['toast'] = (f"{reason} Models retrained using "
                                 f"{result['reports_used']} reported half-hour(s).")
    st.rerun()

data = load_processed_data()
models = load_models()
splits = sorted(models.split_models.keys())

if 'toast' in st.session_state:
    st.toast(st.session_state.pop('toast'))


# ----------------------------------------------------------------------------- prediction
def build_hints(split_id: str, day: date) -> pd.DataFrame:
    """The 13 hints for every opening-hours slot on `day` (see src/forecast_service.py)."""
    return fs.build_hints(data, split_id, day)

def predict_day(split_id: str, day: date) -> pd.Series:
    """Predicted people for each opening-hours slot. Index = slot number."""
    return fs.predict_day(data, models, split_id, day)

def crowd_level(value: float, peak: float) -> str:
    """Compared with the busiest half hour of that day for this workout."""
    ratio = value / peak if peak > 0 else 0
    return "Quiet" if ratio < 0.4 else ("Moderate" if ratio < 0.75 else "Busy")

def people(n: float) -> str:
    return f"{n:.0f} {'person' if round(n) == 1 else 'people'}"


def dot(color: str) -> str:
    return f'<span class="ios-dot" style="background:{color}"></span>'

def day_word(d: date) -> str:
    if d == date.today():
        return "today"
    if d == date.today() + timedelta(days=1):
        return "tomorrow"
    return "on " + d.strftime("%A")

def day_label(d: date) -> str:
    return day_word(d).replace("on ", "").capitalize() if d <= date.today() + timedelta(days=1) \
        else d.strftime("%a %d %b")

def steps(n: int):
    bars = "".join(f'<i class="{"on" if i <= n else ""}"></i>' for i in (1, 2))
    st.markdown(f'<div class="ios-step-label">Step {n} of 2</div><div class="ios-steps">{bars}</div>',
                unsafe_allow_html=True)

def header(text: str):
    st.markdown(f'<div class="ios-h">{text}</div>', unsafe_allow_html=True)

def default_slot() -> int:
    """Next half hour from now, if the gym is open; otherwise 18:00."""
    now = datetime.now()
    slot = now.hour * 2 + (1 if now.minute >= 30 else 0) + 1
    return slot if OPEN_SLOTS[0] <= slot <= OPEN_SLOTS[-1] else 36


# ----------------------------------------------------------------------------- state
st.session_state.setdefault('step', 1)
st.session_state.setdefault('pref_slot', default_slot())
default_split = "Chest" if "Chest" in splits else splits[0]


# ============================================================================= STEP 1
if st.session_state.step == 1:
    steps(1)
    st.markdown('<div class="ios-title">Plan your session</div>'
                '<div class="ios-subtitle">Pick a body group and the time you\'d like to go.</div>',
                unsafe_allow_html=True)

    header("Body group")
    st.pills("Body group", splits, default=st.session_state.get('split', default_split),
             key="workout", label_visibility="collapsed")

    header("Preferred time")
    st.session_state.pref_slot = time_wheel(st.session_state.pref_slot, key="wheel")
    st.markdown('<div class="ios-foot">Scroll to pick. The gym is open 06:00 – 22:00.</div>',
                unsafe_allow_html=True)

    st.write("")
    if st.button("Next", type="primary", use_container_width=True, key="next"):
        # Streamlit forgets a widget's value once it's off screen, so keep a copy for step 2
        st.session_state.split = st.session_state.get('workout') or default_split
        st.session_state.step = 2
        st.rerun()


# ============================================================================= STEP 2
else:
    split = st.session_state.get('split', default_split)
    pref = st.session_state.pref_slot

    if st.button("‹ Back", type="tertiary", key="back"):
        st.session_state.step = 1
        st.rerun()
    steps(2)
    st.markdown(f'<div class="ios-title">Your slot</div>'
                f'<div class="ios-subtitle">{split} · you picked {slot_to_time(pref)}</div>',
                unsafe_allow_html=True)

    next_days = [date.today() + timedelta(days=i) for i in range(7)]
    day = st.selectbox("Day", next_days, format_func=day_label, key="day")

    # --- find the best time near the preferred one
    preds = predict_day(split, day)
    peak, peak_slot = preds.max(), preds.idxmax()
    nearby = [s for s in range(pref - SEARCH, pref + SEARCH + 1) if s in preds.index]
    # quietest first; if two are equal, the one closer to your time wins
    best = min(nearby, key=lambda s: (round(preds[s], 1), abs(s - pref)))
    if preds[pref] - preds[best] < SAME_ENOUGH:
        best = pref                      # not worth moving for less than half a person
    bv, pv = preds[best], preds[pref]
    level = crowd_level(bv, peak)

    # --- hero
    title = "Your time is the best one" if best == pref else "Best time near your pick"
    st.markdown(
        f'<div class="ios-hero"><div class="k">{title}</div>'
        f'<div class="v">{slot_to_time(best)}</div>'
        f'<div class="s">{dot(CROWD_COLORS[level])}{level} · about {people(bv)}</div>'
        f'<div class="p">{split} · {day_label(day)}</div></div>', unsafe_allow_html=True)

    # --- reasons (all from the model's numbers)
    reasons = []
    if best == pref:
        reasons.append(("✓", GREEN, "Nothing nearby is quieter",
                        f"Within 90 minutes of {slot_to_time(pref)}, no time saves you even half a person."))
    else:
        mins = abs(best - pref) * 30
        gap = f"{mins} min" if mins < 60 else f"{mins // 60} h" + (f" {mins % 60} min" if mins % 60 else "")
        reasons.append(("↓", GREEN, f"{pv - bv:.0f} fewer {'person' if round(pv - bv) == 1 else 'people'} "
                                    f"than {slot_to_time(pref)}",
                        f"About {people(bv)} instead of {people(pv)}."))
        reasons.append(("⏱", BLUE, f"{gap} {'later' if best > pref else 'earlier'} than you picked",
                        f"The quietest time within 90 minutes of {slot_to_time(pref)}."))
    reasons.append(("●", CROWD_COLORS[level], f"{level} for {split.lower()} {day_word(day)}",
                    f"The busiest time is {slot_to_time(peak_slot)}, with about {people(peak)}."))
    past = data[(data['split_id'] == split) & (data['time_slot'] == best) &
                (data['date'].dt.dayofweek == pd.Timestamp(day).dayofweek) &
                (data['date'] < pd.Timestamp(day))]['visitor_count']
    if len(past):
        weekday = pd.Timestamp(day).strftime("%A")
        reasons.append(("↺", GREY, f"Past {weekday}s at {slot_to_time(best)}",
                        f"About {past.mean():.1f} people on average over {len(past)} weeks."))

    header("Why this time")
    st.markdown('<div class="ios-list">' + "".join(
        f'<div class="ios-row"><div class="ios-icon" style="background:{c};color:{P["on_accent"] if c == BLUE else "#fff"}">{icon}</div>'
        f'<div class="txt"><div class="t1">{t1}</div><div class="t2">{t2}</div></div></div>'
        for icon, c, t1, t2 in reasons) + '</div>', unsafe_allow_html=True)

    # --- nearby times
    header("Nearby times")
    rows = []
    for s in nearby:
        lv = crowd_level(preds[s], peak)
        badge = ""
        if s == best:
            badge = f'<span class="ios-badge" style="background:{BLUE};color:{P["on_accent"]}">Best</span>'
        elif s == pref:
            badge = f'<span class="ios-badge" style="background:{P["chip"]};color:{P["chip_ink"]}">Your pick</span>'
        rows.append(f'<div class="ios-row{" hl" if s == best else ""}"><div class="time">{slot_to_time(s)}</div>'
                    f'<div class="ppl">about {people(preds[s])}</div>{badge}{dot(CROWD_COLORS[lv])}</div>')
    st.markdown('<div class="ios-list plain">' + "".join(rows) + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="ios-foot">Green = quiet, yellow = moderate, red = busy, '
                'compared with the busiest time that day.</div>', unsafe_allow_html=True)

    st.write("")
    if st.button(f"I'm going at {slot_to_time(best)}", type="primary", use_container_width=True, key="go"):
        collector.collect_prediction_feedback(day, split, best, bv)
        st.session_state['toast'] = (f"See you at {slot_to_time(best)} {day_word(day)}. "
                                     "Log the crowd afterwards to help the forecast.")
        st.rerun()

    # --- extras
    header("More")
    with st.expander("See the whole day"):
        labels = [slot_to_time(s) for s in OPEN_SLOTS]
        colors = [CROWD_COLORS[crowd_level(v, peak)] for v in preds.values]
        opacity = [1.0 if s in nearby else 0.35 for s in OPEN_SLOTS]
        fig = go.Figure(go.Bar(x=labels, y=preds.values, marker=dict(color=colors, opacity=opacity),
                               hovertemplate="%{x}: about %{y:.1f} people<extra></extra>"))
        fig.update_layout(height=220, margin=dict(l=0, r=0, t=8, b=0), showlegend=False, bargap=0.25,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          font=dict(family="-apple-system, Helvetica Neue, Arial, sans-serif", color=GREY, size=11),
                          yaxis=dict(rangemode="tozero", gridcolor="rgba(235,235,245,.08)", zeroline=False),
                          xaxis=dict(tickmode="array", tickvals=labels[::8], tickangle=0, showgrid=False))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Bright bars = the times around your pick. The gym is closed 22:30 – 06:00.")

    with st.expander("Log the crowd"):
        st.caption("Were you at the gym? Tell us how many people were doing your workout.")
        with st.form("report_form", clear_on_submit=False):
            r_split = st.selectbox("Body group", splits, index=splits.index(split), key="report_workout")
            r_date = st.date_input("Day", value=date.today(), max_value=date.today(), key="report_day")
            r_time = st.selectbox("Time", [slot_to_time(s) for s in OPEN_SLOTS],
                                  index=OPEN_SLOTS.index(pref), key="report_time")
            r_count = st.number_input("People there", min_value=0, max_value=500, value=10, key="report_count")
            submitted = st.form_submit_button("Log it", use_container_width=True, type="primary")
        if submitted:
            slot = int(r_time[:2]) * 2 + int(r_time[3:]) // 30
            try:
                collector.report_attendance(r_date, r_split, slot, r_count)
            except ValueError as e:
                st.error(f"Not saved: {e}")
            else:
                if learner.should_retrain():
                    retrain_and_reload(f"{learner.retrain_every} new reports collected.")
                load_processed_data.clear()   # the new number feeds the hints right away
                left = learner.retrain_every - learner.pending_count()
                st.session_state['toast'] = (f"Logged: {r_split}, {r_date:%d %b} {r_time}, {r_count} people. "
                                             f"{left} more until the forecast retrains.")
                st.rerun()

    with st.expander("How the forecast works"):
        summary = learner.get_feedback_summary()
        st.write("For each body group, three models (XGBoost, Random Forest and Linear Regression) "
                 "predict the crowd for every half hour. The app then looks 90 minutes either side of "
                 "your preferred time and picks the quietest, unless it saves less than half a person.")
        ev = load_evaluation()
        if ev:
            table = pd.DataFrame(ev['workouts']).T[['mae', 'r2']]
            table.columns = ['Avg miss (people)', 'R²']
            st.dataframe(table.style.format('{:.2f}'), use_container_width=True)
            st.caption(f"Tested on days the models never saw, {pd.to_datetime(ev['evaluated_at']):%d %b %Y}.")
        st.caption(f"Crowds logged: {summary['total_feedback']} · waiting to be learned: "
                   f"{summary['pending_feedback']}/{summary['retrain_every']}")
        if st.button("Retrain now", use_container_width=True):
            retrain_and_reload("Retrained on request.")
