// Tests for the recommendation rule. Run with:  flutter test
//
// golden_cases.json holds 168 answers worked out by the original Python app
// (same forecasts as assets/demo/forecasts.json). The Dart version must agree.

import 'dart:convert';
import 'dart:io';

import 'package:fit_forecaster/logic/recommendation.dart';
import 'package:fit_forecaster/models/forecast.dart';
import 'package:flutter_test/flutter_test.dart';

DayForecast _make(List<double> people, {String split = 'Legs'}) => DayForecast(
      split: split,
      day: DateTime(2026, 10, 9),
      slots: [for (var i = 0; i < people.length; i++) SlotForecast(slot: firstSlot + i, people: people[i])],
    );

void main() {
  group('slotToTime', () {
    test('turns slot numbers into clock times', () {
      expect(slotToTime(12), '06:00');
      expect(slotToTime(37), '18:30');
      expect(slotToTime(44), '22:00');
    });
  });

  group('crowdLevel', () {
    test('compares with the busiest half hour', () {
      expect(crowdLevel(3, 10), Crowd.quiet); // 30%
      expect(crowdLevel(5, 10), Crowd.moderate); // 50%
      expect(crowdLevel(8, 10), Crowd.busy); // 80%
      expect(crowdLevel(0, 0), Crowd.quiet); // empty day
    });
  });

  group('recommend', () {
    test('moves you to a quieter time nearby', () {
      // 06:00 .. 22:00 = 33 slots; make 19:30 (slot 39) busy and 20:30 (slot 41) empty
      final people = List<double>.filled(33, 5);
      people[39 - firstSlot] = 6;
      people[41 - firstSlot] = 1;
      final rec = recommend(_make(people), 39, dayWord: 'today', weekday: 'Friday');
      expect(rec.best.slot, 41);
      expect(rec.reasons.first.title, '5 fewer people than 19:30');
      expect(rec.reasons[1].title, '1 h later than you picked');
    });

    test('keeps your time if moving saves less than half a person', () {
      final people = List<double>.filled(33, 5);
      people[40 - firstSlot] = 4.7; // only 0.3 quieter
      final rec = recommend(_make(people), 39, dayWord: 'today', weekday: 'Friday');
      expect(rec.keptYourTime, isTrue);
      expect(rec.reasons.first.kind, ReasonKind.nothingQuieter);
    });

    test('on a tie, the time closer to yours wins', () {
      final people = List<double>.filled(33, 5);
      people[37 - firstSlot] = 1; // 1 hour earlier
      people[40 - firstSlot] = 1; // 30 min later: closer to 19:30
      final rec = recommend(_make(people), 39, dayWord: 'today', weekday: 'Friday');
      expect(rec.best.slot, 40);
    });

    test('never looks outside opening hours', () {
      final people = List<double>.filled(33, 5);
      final rec = recommend(_make(people), lastSlot, dayWord: 'today', weekday: 'Friday');
      expect(rec.nearby.map((s) => s.slot), [41, 42, 43, 44]);
    });
  });

  group('the board on step 2', () {
    Recommendation recFor(List<double> people, int pref) =>
        recommend(_make(people), pref, dayWord: 'today', weekday: 'Friday');

    test('shows your time down to the best time, at least 4 rows', () {
      final people = List<double>.filled(33, 5);
      people[39 - firstSlot] = 5; // 19:30, your pick
      people[42 - firstSlot] = 1; // 21:00, best
      final rows = boardRows(recFor(people, 39));
      expect(rows.map((s) => s.time), ['19:30', '20:00', '20:30', '21:00']);
    });

    test('tops up with later times when the best is right next to yours', () {
      final people = List<double>.filled(33, 5);
      people[40 - firstSlot] = 1; // 20:00 is best, right after 19:30
      final rows = boardRows(recFor(people, 39));
      expect(rows.map((s) => s.time), ['19:30', '20:00', '20:30', '21:00']);
    });

    test('at closing time it tops up with earlier times instead', () {
      final people = List<double>.filled(33, 5);
      final rows = boardRows(recFor(people, lastSlot)); // 22:00, nothing quieter
      expect(rows.map((s) => s.time), ['20:30', '21:00', '21:30', '22:00']);
    });

    test('the note and the reason read naturally', () {
      final people = List<double>.filled(33, 9);
      people[39 - firstSlot] = 5;
      people[42 - firstSlot] = 2;
      final rec = recFor(people, 39);
      expect(boardNote(rec), 'only 2 people!');
      final (a, b, c) = boardWhy(rec);
      expect('$a$b$c', '3 fewer than 19:30, just 1 h 30 later.');
      expect(b, '1 h 30 later');
    });

    test('says so when your own time is already the quietest', () {
      final people = List<double>.filled(33, 5);
      people[39 - firstSlot] = 1;
      final rec = recFor(people, 39);
      final (a, b, c) = boardWhy(rec);
      expect(rec.keptYourTime, isTrue);
      expect('$a$b$c', 'Nothing within 90 minutes is quieter than your time.');
    });
  });

  test('agrees with the Python app on 168 real forecasts', () {
    final demo = jsonDecode(File('assets/demo/forecasts.json').readAsStringSync()) as Map<String, dynamic>;
    final cases = (jsonDecode(File('test/golden_cases.json').readAsStringSync()) as List).cast<Map<String, dynamic>>();
    final days = (demo['days'] as List).cast<Map<String, dynamic>>();

    for (final c in cases) {
      final day = days.firstWhere((d) => d['weekday'] == c['weekday']);
      final slots = ((day['forecasts'] as Map<String, dynamic>)[c['split']] as List)
          .map((s) => SlotForecast.fromJson(s as Map<String, dynamic>))
          .toList();
      final f = DayForecast(split: c['split'] as String, day: DateTime(2026, 10, 9), slots: slots);
      final rec = recommend(f, c['pref'] as int, dayWord: 'today', weekday: c['weekday'] as String);
      final where = '${c['split']} ${c['weekday']} pref ${slotToTime(c['pref'] as int)}';

      expect(rec.best.slot, c['best'], reason: where);
      expect(rec.level.label, c['level'], reason: where);
      expect(rec.peakSlot, c['peak_slot'], reason: where);
      expect(rec.reasons.map((r) => r.title).toList(), List<String>.from(c['titles'] as List), reason: where);
    }
  });
}
