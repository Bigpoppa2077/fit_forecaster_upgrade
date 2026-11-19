// A first widget test: build step 1 with fake data and tap around.
// Run with:  flutter test

import 'package:fit_forecaster/data/forecast_repository.dart';
import 'package:fit_forecaster/models/forecast.dart';
import 'package:fit_forecaster/screens/plan_screen.dart';
import 'package:fit_forecaster/theme/chalk.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pretends to be the API, so the test needs no server.
class FakeRepo extends ForecastRepository {
  FakeRepo() : super(baseUrl: 'http://fake');

  @override
  Future<List<String>> splits() async => ['Arms', 'Chest', 'Legs'];

  @override
  Future<DayForecast> forecast(String split, DateTime day) async => DayForecast(
        split: split,
        day: day,
        slots: [for (var s = firstSlot; s <= lastSlot; s++) SlotForecast(slot: s, people: s == 41 ? 1 : 6)],
      );
}

void main() {
  testWidgets('step 1 shows body groups and lets you pick one', (tester) async {
    tester.view.physicalSize = const Size(1170, 4200); // a tall phone, so the whole screen is built
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(theme: buildChalkTheme(Brightness.dark), home: PlanScreen(repo: FakeRepo())));
    await tester.pumpAndSettle();

    expect(find.text('Plan your session'), findsOneWidget);
    expect(find.text('Legs'), findsOneWidget);
    await tester.tap(find.text('Legs'));
    await tester.pump();
    expect(find.text('Next'), findsOneWidget);
  });

  test('defaultSlot picks the next half hour, or 18:00 when closed', () {
    expect(defaultSlot(DateTime(2026, 10, 9, 17, 10)), 35); // 17:30
    expect(defaultSlot(DateTime(2026, 10, 9, 23, 0)), 36); // closed -> 18:00
  });
}
