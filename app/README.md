# Fit Forecaster (Flutter app)

Find the quietest time to train, near the time you want. Pick a body group and a time
on an iPhone-style wheel, and the app shows the best half hour within 90 minutes, with
reasons. It runs on Android, iOS, web and desktop from one codebase, and looks like the gym's
chalkboard (or a whiteboard in light mode).

The predictions come from the Python models in [`../backend`](../backend)
(XGBoost + Random Forest + Linear Regression per body group), through a small API.
If the API isn't running, the app uses a saved demo week, so it always works.

```
Flutter app  ──HTTP──▶  api/server.py (FastAPI)  ──▶  the trained models
   (this folder)            (../backend)
```

## Run it

You need Flutter 3.27 or newer: <https://docs.flutter.dev/get-started/install>.
Check with `flutter doctor`.

1. **Add the platform folders** (android, ios, web, windows). They are generated, not
   written by hand, so they aren't included. In this folder run:
   ```
   flutter create . --project-name fit_forecaster --platforms=android,ios,web,windows
   ```
   This only adds missing files; it won't touch `lib/`, `test/` or `pubspec.yaml`.
2. **Get the packages:** `flutter pub get`
3. **Run the tests:** `flutter test`
4. **Start the forecast API** (optional, in the `backend` folder, after `python train_and_test.py`):
   ```
   pip install fastapi uvicorn
   uvicorn api.server:app --host 0.0.0.0 --port 8000
   ```
   Open <http://localhost:8000/docs> to try it in the browser.
5. **Run the app:**
   - In Chrome (easiest): `flutter run -d chrome`
   - On the Android emulator: `flutter run` (it reaches your computer at `10.0.2.2`)
   - On your own phone (same Wi-Fi as your computer):
     `flutter run --dart-define=API_URL=http://YOUR-PC-IP:8000`

**Android note:** Android blocks plain `http://` by default. For local testing, open
`android/app/src/main/AndroidManifest.xml` and add these two parts:
```xml
<uses-permission android:name="android.permission.INTERNET"/>   <!-- above <application> -->
<application android:usesCleartextTraffic="true" ...>           <!-- add the attribute -->
```
Without the API the app still runs, using the demo week.

## What's where

| File | What it does | Flutter idea it teaches |
|---|---|---|
| `lib/main.dart` | Starts the app, light + dark themes | `runApp`, `MaterialApp`, `themeMode` |
| `lib/theme/chalk.dart` | Chalkboard (dark) and whiteboard (light) colours, the app font and text styles | `ThemeData`, `ThemeExtension` |
| `lib/screens/plan_screen.dart` | Step 1: body group + time wheel | `StatefulWidget`, `setState`, `initState`, `Navigator.push` |
| `lib/screens/result_screen.dart` | Step 2: the circled best time, tally marks, two buttons, sheets | `FutureBuilder`, `Text.rich`, `SnackBar`, bottom sheets |
| `lib/logic/recommendation.dart` | The rule that picks the best time, and what goes on the board | Plain Dart: enums, extensions, records |
| `lib/data/forecast_repository.dart` | Calls the API, falls back to demo data | `async`/`await`, `http`, assets, `--dart-define` |
| `lib/widgets/chalk_widgets.dart` | The framed board, buttons, chips, headings, links, day tabs | Composing widgets, `DecorationImage`, `AnimatedScale` |
| `lib/widgets/chalk_drawings.dart` | The scribbled circle, tally marks, dashed lines | `CustomPaint`, `Path`, `Paint` |
| `lib/widgets/time_wheel.dart` | The scroll wheel | `CupertinoPicker`, controllers, `dispose` |
| `lib/widgets/day_bars.dart` | The whole day as chalk bars | `CustomPainter`, `TextPainter` |
| `lib/widgets/theme_switch.dart` | Auto / whiteboard / chalkboard switch | `ValueNotifier`, `ValueListenableBuilder` |
| `test/` | Unit + widget tests (168 answers checked against the Python app) | `flutter_test` |

## The look

**Chalkboard**: the gym's workout board. In dark mode it's chalk on a slate board in a
wooden frame; in light mode it's marker on a whiteboard in an aluminium frame. The app
follows the phone's setting, and the switch in the corner cycles auto, whiteboard and chalkboard.

Step 2 is kept short: the best time circled with a note ("only 2 people!"), one line of
why, your time crossed out, every crowd counted in tally marks (green quiet, yellow
moderate, red busy), and two buttons. The details (all the reasons, the whole day, logging
a crowd) are one tap away.

**Font:** the phone's own font (SF Pro on iPhone, Roboto on Android), like most apps.
The chalk feel comes from the board, the scribbled circle, the tally marks and the dashed
lines; the words stay easy to read. **Inter** (SIL Open Font License) is bundled in
`assets/fonts/`: set `appFont = 'Inter'` in `lib/theme/chalk.dart` to use it instead.
The chalk dust and whiteboard ghost-mark textures in `assets/textures/` were generated for this app.

## Learn Flutter with this app

Do one lesson at a time. For each: read the file, run the app, change one thing, see what happens.

1. **Widgets are the whole UI.** Open `plan_screen.dart`. Everything on screen is a widget
   inside another widget. Try: change the title text, hot reload (press `r`).
2. **Layout.** `Column`, `Row`, `Padding`, `SizedBox`, `Expanded`, `Wrap`. Try: make the
   body groups two per row in `BodyGroupGrid`.
3. **State.** `StatefulWidget` + `setState` (the chosen body group, the wheel's time).
   Try: print the slot in `onChanged` and watch it as you scroll.
4. **Theme.** `chalk.dart`. Try: change the dark board's `highlight` to pink chalk (`0xFFF49AC1`), or set `appFont = 'Inter'`.
5. **Navigation.** `Navigator.push` to step 2 and `pop` back. Try: pass one more value to `ResultScreen`.
6. **Async + API.** `forecast_repository.dart`, `FutureBuilder`. Try: stop the API and watch the demo note appear.
7. **Custom drawing.** `chalk_drawings.dart`. Try: make the circle's stroke thicker, or draw tallies in groups of 10.
8. **Animation.** `AnimatedScale`, `AnimatedContainer`, `AnimatedSize`. Try: slow the button press down.
9. **Tests.** `flutter test`. Try: break the rule on purpose (change `sameEnough` to `2`) and see which tests fail.
10. **Next steps (good practice exercises):** remember the theme choice with
    `shared_preferences`; add a splash screen; build an APK with `flutter build apk`.

## Prompting an AI assistant for Flutter work

Good prompts give the assistant what it can't see. A pattern that works:

> **Context:** Flutter 3.27 app, Material 3, colours in `lib/theme/chalk.dart` (a ThemeExtension, read with `context.chalk`).
> **Task:** add a "Remember my choice" toggle to the theme switch, using `shared_preferences`.
> **Constraints:** keep `ThemeSwitch` stateless; no new state-management package; update the README.
> **Done when:** the choice survives an app restart and `flutter test` passes.

Tips:
- **Paste the file** (or the widget) you want changed, and name the Flutter version.
- **Paste the full error** from `flutter run` or `flutter analyze`, not a summary.
- **Ask for one change at a time**, then run it. Small steps are easier to check.
- **Ask "why"** for anything new: "explain what `late final` does on this line."
- **Ask for a test** with every logic change, then run `flutter test` yourself.
- **Check the answer**: run `flutter analyze`, and read the diff before keeping it.
