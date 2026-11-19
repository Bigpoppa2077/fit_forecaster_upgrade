// Where forecasts come from.
//
// First choice: the Python API (api/server.py in the Fit Forecaster project),
// which runs the real XGBoost / Random Forest / Linear Regression models.
// If the API can't be reached, the app falls back to a week of demo forecasts
// bundled in assets/demo/forecasts.json, so it always has something to show.
//
// Flutter ideas: async/await and Future, the `http` package, reading an asset
// with rootBundle, and compile-time settings with --dart-define.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;

import '../models/forecast.dart';

/// Where the API lives. Override when you run the app:
///   flutter run --dart-define=API_URL=http://192.168.1.20:8000
/// (use your computer's local IP when testing on a real phone).
String apiBaseUrl() {
  const fromBuild = String.fromEnvironment('API_URL');
  if (fromBuild.isNotEmpty) return fromBuild;
  // The Android emulator reaches your computer at 10.0.2.2, not localhost.
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) return 'http://10.0.2.2:8000';
  return 'http://localhost:8000';
}

class ForecastRepository {
  ForecastRepository({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _base = baseUrl ?? apiBaseUrl();

  final http.Client _client;
  final String _base;
  static const _timeout = Duration(seconds: 4);

  /// True once we've had to use the demo file instead of the API.
  bool usingDemo = false;
  Map<String, dynamic>? _demo;

  Future<Map<String, dynamic>> _loadDemo() async =>
      _demo ??= jsonDecode(await rootBundle.loadString('assets/demo/forecasts.json')) as Map<String, dynamic>;

  /// The body groups, e.g. ["Arms", "Back", ...].
  Future<List<String>> splits() async {
    try {
      final res = await _client.get(Uri.parse('$_base/api/splits')).timeout(_timeout);
      if (res.statusCode == 200) {
        usingDemo = false;
        return List<String>.from(jsonDecode(res.body)['splits'] as List);
      }
    } catch (_) {
      // no server: fall through to demo data
    }
    usingDemo = true;
    return List<String>.from((await _loadDemo())['splits'] as List);
  }

  /// Predicted people for every half hour of [day] for one body group.
  Future<DayForecast> forecast(String split, DateTime day) async {
    final dayText = _dateText(day);
    try {
      final uri = Uri.parse('$_base/api/forecast').replace(queryParameters: {'split': split, 'day': dayText});
      final res = await _client.get(uri).timeout(_timeout);
      if (res.statusCode == 200) {
        usingDemo = false;
        return DayForecast.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
      }
    } catch (_) {
      // no server: fall through to demo data
    }
    usingDemo = true;
    return _demoForecast(split, day);
  }

  /// The demo file has one forecast per weekday; use the one for the same weekday.
  Future<DayForecast> _demoForecast(String split, DateTime day) async {
    final demo = await _loadDemo();
    final days = (demo['days'] as List).cast<Map<String, dynamic>>();
    final wanted = _weekdayName(day);
    final match = days.firstWhere((d) => d['weekday'] == wanted, orElse: () => days.first);
    final slots = (match['forecasts'] as Map<String, dynamic>)[split] as List;
    return DayForecast.fromJson({'split': split, 'day': dayText(day), 'slots': slots}, isDemo: true);
  }

  /// "I'm going at 21:00". Returns false if it couldn't be saved (demo mode).
  Future<bool> savePlan(String split, DateTime day, int slot, double predicted) async {
    try {
      final res = await _client
          .post(Uri.parse('$_base/api/plans'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({'day': _dateText(day), 'split': split, 'slot': slot, 'predicted': predicted}))
          .timeout(_timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// "I was there and saw [count] people". Returns a message to show the user.
  Future<String> reportCrowd(String split, DateTime day, int slot, int count) async {
    try {
      final res = await _client
          .post(Uri.parse('$_base/api/reports'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({'day': _dateText(day), 'split': split, 'slot': slot, 'count': count}))
          .timeout(const Duration(seconds: 40)); // a retrain can take a while
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      if (res.statusCode != 200) return 'Not saved: ${body['detail']}';
      if (body['retrained'] == true) return 'Logged. The models just retrained with your reports.';
      final left = (body['retrain_every'] as int) - (body['pending'] as int);
      return 'Logged: $count people at ${slotToTime(slot)}. $left more until the forecast retrains.';
    } catch (_) {
      return "Couldn't reach the forecast server, so this wasn't saved. Start the API and try again.";
    }
  }

  static String _dateText(DateTime d) => dayText(d);
}

/// 2026-10-09
String dayText(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

const _weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
String _weekdayName(DateTime d) => _weekdays[d.weekday - 1];
String weekdayName(DateTime d) => _weekdayName(d);
