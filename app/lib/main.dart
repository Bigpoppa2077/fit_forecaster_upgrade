// Fit Forecaster: find the quietest time to train, near the time you want.
//
// How the app is put together (read in this order):
//   main.dart                     starts the app, light/dark themes
//   theme/chalk.dart              chalkboard (dark) and whiteboard (light) colours + font
//   screens/plan_screen.dart      step 1: body group + time wheel
//   screens/result_screen.dart    step 2: the circled best time, tally marks, two buttons
//   logic/recommendation.dart     the rule that picks the best time (plain Dart, tested)
//   data/forecast_repository.dart talks to the Python API, or uses demo data
//   widgets/                      the board pieces: frame, chips, buttons, circle, tallies, wheel

import 'package:flutter/material.dart';

import 'data/forecast_repository.dart';
import 'screens/plan_screen.dart';
import 'theme/chalk.dart';
import 'widgets/theme_switch.dart';

void main() {
  runApp(FitForecasterApp(repo: ForecastRepository()));
}

class FitForecasterApp extends StatelessWidget {
  const FitForecasterApp({super.key, required this.repo});
  final ForecastRepository repo;

  @override
  Widget build(BuildContext context) {
    // Rebuild the app whenever the Auto / Light / Dark switch changes.
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: themeMode,
      builder: (context, mode, _) => MaterialApp(
        title: 'Fit Forecaster',
        debugShowCheckedModeBanner: false,
        theme: buildChalkTheme(Brightness.light),
        darkTheme: buildChalkTheme(Brightness.dark),
        themeMode: mode, // system = follow the phone's setting
        home: PlanScreen(repo: repo),
      ),
    );
  }
}
