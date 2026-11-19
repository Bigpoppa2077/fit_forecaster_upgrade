// STEP 1: pick a body group and the time you'd like to go.
// Flutter ideas: a screen is just a widget; load data in initState and call
// setState when it arrives (a spinner shows meanwhile); Navigator.push opens
// the next screen.

import 'package:flutter/material.dart';

import '../data/forecast_repository.dart';
import '../models/forecast.dart';
import '../theme/chalk.dart';
import '../widgets/chalk_widgets.dart';
import '../widgets/time_wheel.dart';
import 'result_screen.dart';

class PlanScreen extends StatefulWidget {
  const PlanScreen({super.key, required this.repo});
  final ForecastRepository repo;

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  List<String>? _splits; // null while loading
  String? _split; // chosen body group
  int _slot = defaultSlot(DateTime.now());

  @override
  void initState() {
    super.initState();
    widget.repo.splits().then((splits) {
      if (!mounted) return; // the screen was closed while we waited
      setState(() {
        _splits = splits;
        _split = splits.contains('Chest') ? 'Chest' : splits.first;
      });
    });
  }

  void _next() {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => ResultScreen(repo: widget.repo, split: _split!, preferredSlot: _slot),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return ChalkPage(children: [
      TopRow(left: Text('Step 1 of 2', style: ink(context, 14, color: c.muted))),
      Text('Plan your session', style: ink(context, 31, weight: FontWeight.w800).copyWith(height: 1.1)),
      const SizedBox(height: 4),
      Text('Pick a body group and a time.', style: ink(context, 16, color: c.muted, weight: FontWeight.w400)),
      const ChalkHeading('Body group'),
      if (_splits == null)
        const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
      else
        BodyGroupGrid(splits: _splits!, selected: _split!, onSelected: (s) => setState(() => _split = s)),
      const ChalkHeading('Preferred time'),
      TimeWheel(slot: _slot, onChanged: (s) => setState(() => _slot = s)),
      Padding(
        padding: const EdgeInsets.fromLTRB(4, 6, 4, 20),
        child: Text('The gym is open 06:00 – 22:00.', style: ink(context, 14, color: c.muted, weight: FontWeight.w400)),
      ),
      ChalkButton(label: 'Next', trailing: Icons.arrow_forward_rounded, onPressed: _split == null ? null : _next),
    ]);
  }
}

/// Three boxes per row; if one is left over, it takes the whole row.
class BodyGroupGrid extends StatelessWidget {
  const BodyGroupGrid({super.key, required this.splits, required this.selected, required this.onSelected});
  final List<String> splits;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, box) {
      const gap = 10.0;
      final third = (box.maxWidth - gap * 2) / 3;
      final lonely = splits.length % 3 == 1; // e.g. 7 groups: the last one sits alone
      return Wrap(spacing: gap, runSpacing: gap, children: [
        for (var i = 0; i < splits.length; i++)
          SizedBox(
            width: lonely && i == splits.length - 1 ? box.maxWidth : third,
            child: ChalkChip(label: splits[i], selected: splits[i] == selected, onTap: () => onSelected(splits[i])),
          ),
      ]);
    });
  }
}

/// The next half hour from now if the gym is open, otherwise 18:00.
int defaultSlot(DateTime now) {
  final slot = now.hour * 2 + (now.minute >= 30 ? 1 : 0) + 1;
  return (slot >= firstSlot && slot <= lastSlot) ? slot : 36;
}
