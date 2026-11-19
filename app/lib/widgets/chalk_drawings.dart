// Things drawn by hand on the board: the circle around the best time,
// tally marks for crowd sizes, and dashed lines.
// Flutter ideas: CustomPaint + CustomPainter, Path (moveTo, cubicTo),
// Paint (stroke width, round caps), shouldRepaint.

import 'package:flutter/material.dart';

import '../theme/chalk.dart';

/// The best time, big, with a chalk circle scribbled around it.
class CircledTime extends StatelessWidget {
  const CircledTime({super.key, required this.time});
  final String time;

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return CustomPaint(
      painter: _RingPainter(c.highlight),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(26, 12, 26, 10),
        child: Text(time, style: ink(context, 62, color: c.text, weight: FontWeight.w800, digits: true).copyWith(height: 1)),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    // drawn in a 220 x 110 box, then stretched to fit the time
    final sx = size.width / 220, sy = size.height / 110;
    final path = Path()
      ..moveTo(30 * sx, 18 * sy)
      ..cubicTo(90 * sx, -6 * sy, 190 * sx, 2 * sy, 210 * sx, 40 * sy)
      ..cubicTo(228 * sx, 78 * sy, 160 * sx, 106 * sy, 95 * sx, 104 * sy)
      ..cubicTo(30 * sx, 102 * sy, 0, 78 * sy, 8 * sx, 48 * sy)
      ..cubicTo(14 * sx, 24 * sy, 50 * sx, 10 * sy, 120 * sx, 8 * sy); // overshoot, like a real scribble
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter old) => old.color != color;
}

/// Tally marks: groups of four strokes crossed by a fifth.
/// Very big crowds are capped at [maxMarks] so a row never gets too long.
class Tally extends StatelessWidget {
  const Tally({super.key, required this.count, required this.color, this.maxMarks = 15});
  final int count;
  final Color color;
  final int maxMarks;

  @override
  Widget build(BuildContext context) {
    final shown = count.clamp(0, maxMarks);
    final groups = (shown / 5).ceil();
    return Semantics(
      label: '$count people',
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        CustomPaint(size: Size(groups * 38.0 + 4, 24), painter: _TallyPainter(shown, color)),
        if (count > maxMarks) Text('+', style: ink(context, 16, color: color, weight: FontWeight.w700)),
      ]),
    );
  }
}

class _TallyPainter extends CustomPainter {
  _TallyPainter(this.count, this.color);
  final int count;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.4
      ..strokeCap = StrokeCap.round;
    var x = 4.0;
    for (var g = 0; g < count; g += 5) {
      final inGroup = (count - g).clamp(0, 5);
      for (var i = 0; i < inGroup && i < 4; i++) {
        // slightly slanted strokes, like quick chalk marks
        canvas.drawLine(Offset(x + i * 7 + 1, 3), Offset(x + i * 7, 21), paint);
      }
      if (inGroup == 5) canvas.drawLine(Offset(x - 3, 17), Offset(x + 26, 7), paint);
      x += 38;
    }
  }

  @override
  bool shouldRepaint(covariant _TallyPainter old) => old.count != count || old.color != color;
}

/// A dashed horizontal line (used above and below the chosen time on the wheel).
class DashedLine extends StatelessWidget {
  const DashedLine({super.key, required this.color});
  final Color color;

  @override
  Widget build(BuildContext context) =>
      CustomPaint(size: const Size(double.infinity, 2), painter: _DashPainter(color));
}

class _DashPainter extends CustomPainter {
  _DashPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2;
    for (var x = 0.0; x < size.width; x += 12) {
      canvas.drawLine(Offset(x, 1), Offset((x + 7).clamp(0.0, size.width), 1), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _DashPainter old) => old.color != color;
}
