// STEP 2: the best time near your pick, written on the board.
//
// Kept short on purpose: one circled answer, one line of why, a few rows of
// tally marks, two buttons, three small links. The details live in sheets.
//
// Flutter ideas: FutureBuilder (rebuilds when the forecast arrives),
// Text.rich (one line, two colours), SnackBar, showModalBottomSheet, AnimatedSize.

import 'package:flutter/material.dart';

import '../data/forecast_repository.dart';
import '../logic/recommendation.dart';
import '../models/forecast.dart';
import '../theme/chalk.dart';
import '../widgets/chalk_drawings.dart';
import '../widgets/chalk_widgets.dart';
import '../widgets/day_bars.dart';
import '../widgets/time_wheel.dart';

class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key, required this.repo, required this.split, required this.preferredSlot});
  final ForecastRepository repo;
  final String split;
  final int preferredSlot;

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  final DateTime _today = _dateOnly(DateTime.now());
  late DateTime _day = _today;
  late Future<DayForecast> _forecast = widget.repo.forecast(widget.split, _day);
  bool _showDay = false;
  late int _pref = widget.preferredSlot; // your time; "Pick another time" changes it

  late final List<DateTime> _days = [for (var i = 0; i < 7; i++) DateTime(_today.year, _today.month, _today.day + i)];

  void _pickDay(DateTime d) => setState(() {
        _day = d;
        _forecast = widget.repo.forecast(widget.split, d);
      });

  int get _offset => daysBetween(_today, _day);
  String get _dayWord => switch (_offset) { 0 => 'today', 1 => 'tomorrow', _ => 'on ${weekdayName(_day)}' };

  Color _crowdColor(Crowd level) {
    final c = context.chalk;
    return switch (level) { Crowd.quiet => c.quiet, Crowd.moderate => c.moderate, Crowd.busy => c.busy };
  }

  Future<void> _going(SlotForecast slot) async {
    final saved = await widget.repo.savePlan(widget.split, _day, slot.slot, slot.people);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('See you at ${slot.time} $_dayWord. '
          '${saved ? 'Log the crowd afterwards to help the forecast.' : '(Demo mode, so this was not saved.)'}'),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return ChalkPage(children: [
      TopRow(
        left: Align(
          alignment: Alignment.centerLeft,
          child: InkWell(
            onTap: () => Navigator.of(context).pop(),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.arrow_back_rounded, color: c.text, size: 22),
                const SizedBox(width: 6),
                Flexible(
                  child: Text.rich(
                    TextSpan(children: [
                      TextSpan(text: widget.split, style: ink(context, 16, weight: FontWeight.w700)),
                      TextSpan(
                          text: ' · you picked ${slotToTime(_pref)}',
                          style: ink(context, 16, color: c.muted)),
                    ]),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ]),
            ),
          ),
        ),
      ),
      DayTabs(days: _days, selected: _day, labelOf: (d) => dayLabel(d, _today), onPicked: _pickDay),
      FutureBuilder<DayForecast>(
        future: _forecast,
        builder: (context, snap) {
          if (snap.hasError) {
            return Padding(
              padding: const EdgeInsets.all(24),
              child: Text("Couldn't load the forecast: ${snap.error}", style: ink(context, 15, color: c.busy)),
            );
          }
          if (!snap.hasData) {
            return const Padding(padding: EdgeInsets.all(56), child: Center(child: CircularProgressIndicator()));
          }
          final f = snap.data!;
          final rec = recommend(f, _pref, dayWord: _dayWord, weekday: weekdayName(_day));
          return _board(f, rec);
        },
      ),
    ]);
  }

  Widget _board(DayForecast f, Recommendation rec) {
    final c = context.chalk;
    final (before, gap, after) = boardWhy(rec);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (f.isDemo)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text("demo data: the forecast server isn't running", style: ink(context, 14, color: c.busy)),
        ),
      const SizedBox(height: 18),
      // the answer, circled, with a scribbled note
      Row(children: [
        Flexible(child: FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: CircledTime(time: rec.best.time))),
        const SizedBox(width: 6),
        SizedBox(
          width: 86,
          child: Text(boardNote(rec),
              textAlign: TextAlign.center, style: ink(context, 17, color: c.highlight, weight: FontWeight.w700).copyWith(height: 1.15)),
        ),
      ]),
      const SizedBox(height: 20),
      Text.rich(TextSpan(style: ink(context, 16), children: [
        TextSpan(text: before),
        TextSpan(text: gap, style: TextStyle(color: c.highlight, fontWeight: FontWeight.w700)),
        TextSpan(text: after),
      ])),
      const SizedBox(height: 10),
      for (final s in boardRows(rec)) _row(s, rec),
      const SizedBox(height: 22),
      ChalkButton(label: "I'm going at ${rec.best.time}", onPressed: () => _going(rec.best)),
      const SizedBox(height: 10),
      // the other choices, side by side: keep your own time, or pick a different one
      Row(children: [
        if (!rec.keptYourTime) ...[
          Expanded(child: ChalkButton(label: 'Keep ${rec.preferred.time}', filled: false, onPressed: () => _going(rec.preferred))),
          const SizedBox(width: 10),
        ],
        Expanded(child: ChalkButton(label: 'Pick another time', filled: false, onPressed: _openAnotherSheet)),
      ]),
      const SizedBox(height: 16),
      Wrap(alignment: WrapAlignment.center, spacing: 14, children: [
        ChalkLink(_showDay ? 'Hide the day' : 'Whole day', onTap: () => setState(() => _showDay = !_showDay)),
        ChalkLink('Log the crowd', onTap: () => _openLogSheet(rec.preferred.slot)),
        ChalkLink('How it works', onTap: () => _openHowSheet(rec)),
      ]),
      AnimatedSize(
        duration: const Duration(milliseconds: 220),
        child: _showDay
            ? Padding(padding: const EdgeInsets.only(top: 14), child: DayBars(forecast: f, rec: rec))
            : const SizedBox(width: double.infinity),
      ),
    ]);
  }

  /// One line on the board: time, number, tally marks, and a note.
  Widget _row(SlotForecast s, Recommendation rec) {
    final c = context.chalk;
    final isPick = s.slot == rec.preferred.slot && !rec.keptYourTime;
    final isBest = s.slot == rec.best.slot;
    final color = isBest ? c.highlight : (isPick ? c.muted : c.text);
    final strike = isPick ? TextDecoration.lineThrough : null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [
        SizedBox(width: 66, child: Text(s.time, style: ink(context, 17, color: color, weight: FontWeight.w600, decoration: strike, digits: true))),
        SizedBox(
          width: 30,
          child: Text('${s.people.round()}',
              textAlign: TextAlign.right, style: ink(context, 17, color: color, weight: FontWeight.w600, decoration: strike, digits: true)),
        ),
        const SizedBox(width: 12),
        Tally(count: s.people.round(), color: _crowdColor(rec.levelOf(s))),
        const Spacer(),
        if (isBest)
          Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.arrow_back_rounded, size: 18, color: c.highlight),
            const SizedBox(width: 2),
            Text(rec.keptYourTime ? 'your pick' : 'go', style: ink(context, 14, color: c.highlight, weight: FontWeight.w700)),
          ])
        else if (isPick)
          Text('your pick', style: ink(context, 14, color: c.muted)),
      ]),
    );
  }

  /// "Pick another time": choose a new time on the wheel, then the board re-checks the quietest slot near it.
  void _openAnotherSheet() {
    var chosen = _pref;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        final c = sheetContext.chalk;
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 0, 22, 24),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text('Pick another time', style: ink(sheetContext, 26, weight: FontWeight.w800)),
              const SizedBox(height: 4),
              Text("Scroll to the time you'd rather go. We'll check the quietest slot near it.",
                  style: ink(sheetContext, 15, color: c.muted, weight: FontWeight.w400)),
              const SizedBox(height: 8),
              TimeWheel(slot: chosen, onChanged: (s) => chosen = s),
              const SizedBox(height: 14),
              ChalkButton(
                label: 'Check this time',
                onPressed: () {
                  Navigator.of(sheetContext).pop();
                  setState(() {
                    _pref = chosen;
                    _showDay = false;
                  });
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text("Checked ${slotToTime(chosen)}. Here's the quietest time near it.")),
                  );
                },
              ),
            ]),
          ),
        );
      },
    );
  }

  void _openHowSheet(Recommendation rec) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        final c = context.chalk;
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(22, 0, 22, 26),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('How it works', style: ink(context, 26, weight: FontWeight.w800)),
              const SizedBox(height: 8),
              Text(
                'For each body group, three models (XGBoost, Random Forest and Linear Regression) '
                'predict the crowd for every half hour. The app looks 90 minutes either side of your '
                'time and picks the quietest, unless it saves less than half a person.',
                style: ink(context, 15, color: c.muted, weight: FontWeight.w400),
              ),
              const ChalkHeading('Why this time'),
              for (final r in rec.reasons)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(r.title, style: ink(context, 16, weight: FontWeight.w600)),
                    Text(r.detail, style: ink(context, 14, color: c.muted, weight: FontWeight.w400)),
                  ]),
                ),
              const ChalkHeading('Reading the board'),
              Text('Each mark is one person. Green = quiet, yellow = moderate, red = busy, '
                  'compared with the busiest half hour of that day.', style: ink(context, 14, color: c.muted, weight: FontWeight.w400)),
            ]),
          ),
        );
      },
    );
  }

  void _openLogSheet(int startSlot) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => LogCrowdSheet(
        repo: widget.repo,
        split: widget.split,
        today: _today,
        startSlot: startSlot,
        onDone: (message) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message))),
      ),
    );
  }
}

/// Bottom sheet: "I was at the gym and saw N people doing my workout".
class LogCrowdSheet extends StatefulWidget {
  const LogCrowdSheet({
    super.key,
    required this.repo,
    required this.split,
    required this.today,
    required this.startSlot,
    required this.onDone,
  });
  final ForecastRepository repo;
  final String split;
  final DateTime today;
  final int startSlot;
  final ValueChanged<String> onDone;

  @override
  State<LogCrowdSheet> createState() => _LogCrowdSheetState();
}

class _LogCrowdSheetState extends State<LogCrowdSheet> {
  late int _slot = widget.startSlot;
  int _count = 5;
  bool _yesterday = false;
  bool _saving = false;

  Future<void> _save() async {
    setState(() => _saving = true);
    final t = widget.today;
    final day = _yesterday ? DateTime(t.year, t.month, t.day - 1) : t;
    final message = await widget.repo.reportCrowd(widget.split, day, _slot, _count);
    if (!mounted) return;
    Navigator.of(context).pop();
    widget.onDone(message);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    Widget dayChip(String label, bool yesterday) => Expanded(
          child: ChalkChip(label: label, selected: _yesterday == yesterday, onTap: () => setState(() => _yesterday = yesterday)),
        );
    return Padding(
      padding: EdgeInsets.fromLTRB(22, 0, 22, 24 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Log the crowd', style: ink(context, 26, weight: FontWeight.w800)),
        Text('How many people were doing ${widget.split.toLowerCase()} when you were there?',
            style: ink(context, 15, color: c.muted, weight: FontWeight.w400)),
        const SizedBox(height: 16),
        Row(children: [dayChip('Today', false), const SizedBox(width: 10), dayChip('Yesterday', true)]),
        const SizedBox(height: 14),
        Row(children: [
          Text('Time', style: ink(context, 15, color: c.muted)),
          const Spacer(),
          DropdownButton<int>(
            value: _slot,
            dropdownColor: c.board,
            underline: const SizedBox.shrink(),
            style: ink(context, 19, weight: FontWeight.w600, digits: true),
            items: [for (var s = firstSlot; s <= lastSlot; s++) DropdownMenuItem(value: s, child: Text(slotToTime(s)))],
            onChanged: (s) => setState(() => _slot = s ?? _slot),
          ),
        ]),
        Row(children: [
          Text('People there', style: ink(context, 15, color: c.muted)),
          const Spacer(),
          IconButton(
            onPressed: _count > 0 ? () => setState(() => _count--) : null,
            icon: Icon(Icons.remove_circle_outline, color: c.text),
            tooltip: 'One fewer',
          ),
          SizedBox(width: 48, child: Text('$_count', textAlign: TextAlign.center, style: ink(context, 24, weight: FontWeight.w700, digits: true))),
          IconButton(
            onPressed: _count < 500 ? () => setState(() => _count++) : null,
            icon: Icon(Icons.add_circle_outline, color: c.text),
            tooltip: 'One more',
          ),
        ]),
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Align(alignment: Alignment.centerRight, child: Tally(count: _count, color: c.highlight)),
        ),
        ChalkButton(label: _saving ? 'Saving...' : 'Log it', onPressed: _saving ? null : _save),
      ]),
    );
  }
}

DateTime _dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

/// Whole calendar days from [a] to [b]. Done in UTC so daylight-saving changes can't make a day 23 hours long.
int daysBetween(DateTime a, DateTime b) =>
    DateTime.utc(b.year, b.month, b.day).difference(DateTime.utc(a.year, a.month, a.day)).inDays;

const _shortDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/// "Today", "Tomorrow", "Sun 11"
String dayLabel(DateTime d, DateTime today) {
  final offset = daysBetween(today, d);
  if (offset == 0) return 'Today';
  if (offset == 1) return 'Tomorrow';
  return '${_shortDays[d.weekday - 1]} ${d.day}';
}
