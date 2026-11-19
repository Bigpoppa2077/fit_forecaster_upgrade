// The whole day as chalk bars, drawn by hand with CustomPainter.
// Bars near your time are bright; the rest are faded.

import 'package:flutter/material.dart';

import '../logic/recommendation.dart';
import '../models/forecast.dart';
import '../theme/chalk.dart';

class DayBars extends StatelessWidget {
  const DayBars({super.key, required this.forecast, required this.rec});
  final DayForecast forecast;
  final Recommendation rec;

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return Semantics(
      label: 'Crowd for the whole day. Busiest at ${slotToTime(rec.peakSlot)}.',
      child: CustomPaint(
        size: const Size(double.infinity, 150),
        painter: _BarsPainter(
          forecast: forecast,
          rec: rec,
          colors: {Crowd.quiet: c.quiet, Crowd.moderate: c.moderate, Crowd.busy: c.busy},
          labelColor: c.muted,
        ),
      ),
    );
  }
}

class _BarsPainter extends CustomPainter {
  _BarsPainter({required this.forecast, required this.rec, required this.colors, required this.labelColor});
  final DayForecast forecast;
  final Recommendation rec;
  final Map<Crowd, Color> colors;
  final Color labelColor;

  @override
  void paint(Canvas canvas, Size size) {
    const labelSpace = 22.0;
    final slots = forecast.slots;
    final chartH = size.height - labelSpace;
    final slotW = size.width / slots.length;
    final peak = rec.peak <= 0 ? 1.0 : rec.peak;
    final nearby = {for (final s in rec.nearby) s.slot};

    for (var i = 0; i < slots.length; i++) {
      final s = slots[i];
      final h = (s.people / peak) * (chartH - 4);
      final paint = Paint()
        ..color = colors[rec.levelOf(s)]!.withValues(alpha: nearby.contains(s.slot) ? 1 : .35)
        ..strokeWidth = slotW * .55
        ..strokeCap = StrokeCap.round;
      // a single thick chalk stroke per half hour
      final x = i * slotW + slotW / 2;
      if (h > 1) canvas.drawLine(Offset(x, chartH), Offset(x + 1.5, chartH - h), paint);
    }

    // time labels every 4 hours
    for (var i = 0; i < slots.length; i += 8) {
      final tp = TextPainter(
        text: TextSpan(text: slots[i].time, style: TextStyle(fontFamily: appFont, color: labelColor, fontSize: 11, fontWeight: FontWeight.w500)),
        textDirection: TextDirection.ltr,
      )..layout();
      final x = (i * slotW + slotW / 2 - tp.width / 2).clamp(0.0, size.width - tp.width);
      tp.paint(canvas, Offset(x, chartH + 4));
    }
  }

  @override
  bool shouldRepaint(covariant _BarsPainter old) => old.forecast != forecast || old.colors != colors;
}
