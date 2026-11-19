// The recommendation rule, in plain Dart (no widgets), so it is easy to test.
// It is the same rule as the Streamlit app (app.py):
//
//   1. Look 90 minutes either side of the time you picked (3 half hours).
//   2. Take the quietest of those. If two are equal, the one closer to your time wins.
//   3. If it saves you less than half a person, keep your own time.
//   4. Explain the choice with reasons built only from the model's numbers.

import '../models/forecast.dart';

const int searchSlots = 3; // 3 half hours = 90 minutes each way
const double sameEnough = 0.5; // less than half a person quieter is not worth moving

enum Crowd { quiet, moderate, busy }

extension CrowdLabel on Crowd {
  String get label => switch (this) {
        Crowd.quiet => 'Quiet',
        Crowd.moderate => 'Moderate',
        Crowd.busy => 'Busy',
      };
}

/// Compared with the busiest half hour of that day for this workout.
Crowd crowdLevel(double value, double peak) {
  final ratio = peak > 0 ? value / peak : 0.0;
  if (ratio < 0.4) return Crowd.quiet;
  if (ratio < 0.75) return Crowd.moderate;
  return Crowd.busy;
}

/// "1 person", "2 people"
String people(double n) => '${n.round()} ${n.round() == 1 ? 'person' : 'people'}';

enum ReasonKind { nothingQuieter, fewer, moved, level, past }

class Reason {
  const Reason(this.kind, this.title, this.detail);
  final ReasonKind kind;
  final String title;
  final String detail;
}

class Recommendation {
  const Recommendation({
    required this.preferred,
    required this.best,
    required this.peak,
    required this.peakSlot,
    required this.nearby,
    required this.reasons,
  });

  final SlotForecast preferred;
  final SlotForecast best;
  final double peak;
  final int peakSlot;
  final List<SlotForecast> nearby; // the times we compared, in order
  final List<Reason> reasons;

  bool get keptYourTime => best.slot == preferred.slot;
  Crowd get level => crowdLevel(best.people, peak);
  Crowd levelOf(SlotForecast s) => crowdLevel(s.people, peak);
}

double _round1(double x) => (x * 10).round() / 10;

/// [dayWord] is "today", "tomorrow" or "on Monday"; [weekday] is "Monday".
Recommendation recommend(DayForecast f, int preferredSlot, {required String dayWord, required String weekday}) {
  final bySlot = f.bySlot;
  final pref = bySlot[preferredSlot] ?? f.slots.first;

  // busiest half hour (the first one if there is a tie)
  var peakSlot = f.slots.first;
  for (final s in f.slots) {
    if (s.people > peakSlot.people) peakSlot = s;
  }
  final peak = peakSlot.people;

  final nearby = [
    for (var s = pref.slot - searchSlots; s <= pref.slot + searchSlots; s++)
      if (bySlot.containsKey(s)) bySlot[s]!,
  ];

  // quietest first; if two are equal, the one closer to your time wins
  var best = nearby.reduce((a, b) {
    final ka = _round1(a.people), kb = _round1(b.people);
    if (ka != kb) return ka < kb ? a : b;
    return (a.slot - pref.slot).abs() <= (b.slot - pref.slot).abs() ? a : b;
  });
  if (pref.people - best.people < sameEnough) best = pref; // not worth moving

  final level = crowdLevel(best.people, peak);
  final reasons = <Reason>[];
  if (best.slot == pref.slot) {
    reasons.add(Reason(ReasonKind.nothingQuieter, 'Nothing nearby is quieter',
        'Within 90 minutes of ${pref.time}, no time saves you even half a person.'));
  } else {
    final saved = pref.people - best.people;
    reasons.add(Reason(ReasonKind.fewer, '${saved.round()} fewer ${saved.round() == 1 ? 'person' : 'people'} than ${pref.time}',
        'About ${people(best.people)} instead of ${people(pref.people)}.'));
    final mins = (best.slot - pref.slot).abs() * 30;
    final gap = mins < 60 ? '$mins min' : '${mins ~/ 60} h${mins % 60 > 0 ? ' ${mins % 60} min' : ''}';
    reasons.add(Reason(ReasonKind.moved, '$gap ${best.slot > pref.slot ? 'later' : 'earlier'} than you picked',
        'The quietest time within 90 minutes of ${pref.time}.'));
  }
  reasons.add(Reason(ReasonKind.level, '${level.label} for ${f.split.toLowerCase()} $dayWord',
      'The busiest time is ${peakSlot.time}, with about ${people(peak)}.'));
  if (best.pastWeeks > 0 && best.pastAvg != null) {
    reasons.add(Reason(ReasonKind.past, 'Past ${weekday}s at ${best.time}',
        'About ${best.pastAvg!.toStringAsFixed(1)} people on average over ${best.pastWeeks} weeks.'));
  }

  return Recommendation(
    preferred: pref,
    best: best,
    peak: peak,
    peakSlot: peakSlot.slot,
    nearby: nearby,
    reasons: reasons,
  );
}

// ---------------------------------------------------------------- the board on step 2

/// The rows written on the board: from your time to the best time (in time order),
/// topped up from the nearby times until there are [minRows], so there's always context.
List<SlotForecast> boardRows(Recommendation rec, {int minRows = 4}) {
  final lo = rec.preferred.slot < rec.best.slot ? rec.preferred.slot : rec.best.slot;
  final hi = rec.preferred.slot < rec.best.slot ? rec.best.slot : rec.preferred.slot;
  var from = lo, to = hi;
  final slots = {for (final s in rec.nearby) s.slot};
  bool grow() {
    // add one row: after the range first (later times), otherwise before it
    if (slots.contains(to + 1)) {
      to++;
      return true;
    }
    if (slots.contains(from - 1)) {
      from--;
      return true;
    }
    return false;
  }

  while (to - from + 1 < minRows && grow()) {}
  return [for (final s in rec.nearby) if (s.slot >= from && s.slot <= to) s];
}

/// The scribble next to the circled time: "only 2 people!", "about 4 people", "busy: 7 people".
String boardNote(Recommendation rec) => switch (rec.level) {
      Crowd.quiet => 'only ${people(rec.best.people)}!',
      Crowd.moderate => 'about ${people(rec.best.people)}',
      Crowd.busy => 'busy: ${people(rec.best.people)}',
    };

/// The one-line reason under the time, split so the time gap can be highlighted:
/// ("3 fewer than 19:30, just ", "1 h 30 later", ".")
(String, String, String) boardWhy(Recommendation rec) {
  if (rec.keptYourTime) return ('Nothing within 90 minutes is ', 'quieter', ' than your time.');
  final saved = (rec.preferred.people - rec.best.people).round();
  final mins = (rec.best.slot - rec.preferred.slot).abs() * 30;
  final gap = mins < 60 ? '$mins min' : '${mins ~/ 60} h${mins % 60 > 0 ? ' ${mins % 60}' : ''}';
  final dir = rec.best.slot > rec.preferred.slot ? 'later' : 'earlier';
  return ('$saved fewer than ${rec.preferred.time}, just ', '$gap $dir', '.');
}
