// Plain data classes for what the API sends back.
// Flutter idea: turning JSON (a Map) into typed Dart objects with fromJson.

/// One half hour of one day. slot 42 = 21:00 (slot = hour * 2, +1 for :30).
class SlotForecast {
  const SlotForecast({
    required this.slot,
    required this.people,
    this.pastAvg,
    this.pastWeeks = 0,
  });

  final int slot;
  final double people; // what the models predict
  final double? pastAvg; // real average on this weekday in earlier weeks
  final int pastWeeks; // how many weeks that average covers

  String get time => slotToTime(slot);

  factory SlotForecast.fromJson(Map<String, dynamic> j) => SlotForecast(
        slot: (j['slot'] as num).toInt(),
        people: (j['people'] as num).toDouble(),
        pastAvg: (j['past_avg'] as num?)?.toDouble(),
        pastWeeks: (j['past_weeks'] as num?)?.toInt() ?? 0,
      );
}

/// The forecast for one body group on one day.
class DayForecast {
  const DayForecast({
    required this.split,
    required this.day,
    required this.slots,
    this.isDemo = false,
  });

  final String split; // e.g. "Legs"
  final DateTime day;
  final List<SlotForecast> slots; // 06:00 .. 22:00
  final bool isDemo; // true when it came from the bundled demo file

  /// slot number -> forecast, for quick lookups
  Map<int, SlotForecast> get bySlot => {for (final s in slots) s.slot: s};

  factory DayForecast.fromJson(Map<String, dynamic> j, {bool isDemo = false}) => DayForecast(
        split: j['split'] as String,
        day: DateTime.parse(j['day'] as String),
        slots: (j['slots'] as List).map((s) => SlotForecast.fromJson(s as Map<String, dynamic>)).toList(),
        isDemo: isDemo,
      );
}

/// 37 -> "18:30"
String slotToTime(int slot) {
  final h = (slot ~/ 2).toString().padLeft(2, '0');
  final m = slot.isOdd ? '30' : '00';
  return '$h:$m';
}

/// Gym opening hours, as slots: 06:00 (12) to 22:00 (44).
const int firstSlot = 12;
const int lastSlot = 44;
