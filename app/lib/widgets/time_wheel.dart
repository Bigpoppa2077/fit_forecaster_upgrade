// The iPhone-alarm style time picker: an hours wheel and a minutes wheel,
// written in chalk, with dashed lines around the chosen time.
// Flutter ideas: CupertinoPicker (Flutter's built-in iOS wheel),
// FixedExtentScrollController, dispose, and passing a value up with a callback.

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../models/forecast.dart';
import '../theme/chalk.dart';
import 'chalk_drawings.dart';

class TimeWheel extends StatefulWidget {
  const TimeWheel({super.key, required this.slot, required this.onChanged});
  final int slot; // 37 = 18:30
  final ValueChanged<int> onChanged;

  @override
  State<TimeWheel> createState() => _TimeWheelState();
}

class _TimeWheelState extends State<TimeWheel> {
  static const _itemHeight = 46.0;
  final _hours = [for (var h = firstSlot ~/ 2; h <= lastSlot ~/ 2; h++) h]; // 6..22
  late final FixedExtentScrollController _hourCtrl;
  late final FixedExtentScrollController _minCtrl;
  late int _hour;
  late int _half; // 0 = :00, 1 = :30

  @override
  void initState() {
    super.initState();
    _hour = widget.slot ~/ 2;
    _half = widget.slot % 2;
    _hourCtrl = FixedExtentScrollController(initialItem: _hours.indexOf(_hour));
    _minCtrl = FixedExtentScrollController(initialItem: _half);
  }

  @override
  void dispose() {
    _hourCtrl.dispose();
    _minCtrl.dispose();
    super.dispose();
  }

  void _changed() {
    var slot = _hour * 2 + _half;
    if (slot > lastSlot) {
      // 22:30 is after closing: snap the minutes wheel back to :00
      _half = 0;
      slot = lastSlot;
      _minCtrl.animateToItem(0, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
    }
    widget.onChanged(slot);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    final style = ink(context, 30, weight: FontWeight.w600, digits: true);

    Widget wheel(FixedExtentScrollController ctrl, List<String> labels, ValueChanged<int> onPick) => CupertinoPicker(
          scrollController: ctrl,
          itemExtent: _itemHeight,
          diameterRatio: 1.4,
          squeeze: 1.05,
          selectionOverlay: const SizedBox.shrink(), // we draw dashed lines instead
          onSelectedItemChanged: onPick,
          children: [for (final l in labels) Center(child: Text(l, style: style))],
        );

    return SizedBox(
      height: _itemHeight * 5,
      child: Stack(alignment: Alignment.center, children: [
        // dashed lines above and below the chosen time
        Column(mainAxisSize: MainAxisSize.min, children: [
          DashedLine(color: c.line),
          const SizedBox(height: _itemHeight - 4),
          DashedLine(color: c.line),
        ]),
        Row(children: [
          const Spacer(),
          SizedBox(
            width: 92,
            child: wheel(_hourCtrl, [for (final h in _hours) h.toString().padLeft(2, '0')], (i) {
              _hour = _hours[i];
              _changed();
            }),
          ),
          Text(':', style: style),
          SizedBox(
            width: 92,
            child: wheel(_minCtrl, const ['00', '30'], (i) {
              _half = i;
              _changed();
            }),
          ),
          const Spacer(),
        ]),
      ]),
    );
  }
}
