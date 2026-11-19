// The building blocks of the board: the framed page, buttons, chips,
// headings, links and the day tabs.
// Flutter ideas: composing small StatelessWidgets, BoxDecoration with a
// tiled DecorationImage (the chalk dust), elliptical BorderRadius (the
// wobbly hand-drawn edges), AnimatedScale for a press effect.

import 'package:flutter/material.dart';

import '../theme/chalk.dart';
import 'theme_switch.dart';

/// Wobbly corners, like a box drawn by hand.
const handRadius = BorderRadius.only(
  topLeft: Radius.elliptical(60, 8),
  topRight: Radius.elliptical(8, 26),
  bottomRight: Radius.elliptical(60, 8),
  bottomLeft: Radius.elliptical(8, 26),
);

/// Every screen: a board inside a frame, a phone-width column that scrolls.
class ChalkPage extends StatelessWidget {
  const ChalkPage({super.key, required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return Scaffold(
      body: SafeArea(
        child: Container(
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: c.board,
            border: Border.all(color: c.frameEdge, width: 2),
            borderRadius: BorderRadius.circular(6),
            image: DecorationImage(image: AssetImage(c.texture), repeat: ImageRepeat.repeat),
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: ListView(padding: const EdgeInsets.fromLTRB(18, 6, 18, 32), children: children),
            ),
          ),
        ),
      ),
    );
  }
}

/// A row at the top: something on the left, the Auto / Light / Dark switch on the right.
class TopRow extends StatelessWidget {
  const TopRow({super.key, required this.left});
  final Widget left;

  @override
  Widget build(BuildContext context) => Row(children: [Expanded(child: left), const ThemeSwitch()]);
}

/// A section heading in blue chalk.
class ChalkHeading extends StatelessWidget {
  const ChalkHeading(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 22, bottom: 8),
        child: Text(text, style: ink(context, 15, color: context.chalk.label, weight: FontWeight.w600)),
      );
}

/// Big button. Filled = the main action; outlined = the other choice.
class ChalkButton extends StatefulWidget {
  const ChalkButton({super.key, required this.label, required this.onPressed, this.filled = true, this.trailing});
  final String label;
  final VoidCallback? onPressed; // null = disabled
  final bool filled;
  final IconData? trailing; // e.g. an arrow after "Next"

  @override
  State<ChalkButton> createState() => _ChalkButtonState();
}

class _ChalkButtonState extends State<ChalkButton> {
  bool _down = false; // is a finger on the button right now?

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    final enabled = widget.onPressed != null;
    final fg = widget.filled ? c.buttonInk : c.text;
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      excludeSemantics: true,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _down = true) : null,
        onTapUp: enabled ? (_) => setState(() => _down = false) : null,
        onTapCancel: enabled ? () => setState(() => _down = false) : null,
        onTap: widget.onPressed,
        child: AnimatedScale(
          scale: _down ? .97 : 1,
          duration: const Duration(milliseconds: 90),
          child: Opacity(
            opacity: enabled ? 1 : .45,
            child: Container(
              height: widget.filled ? 58 : 50,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: widget.filled ? c.button : Colors.transparent,
                borderRadius: handRadius,
                border: widget.filled ? null : Border.all(color: c.line, width: 2),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(widget.label, style: ink(context, widget.filled ? 18 : 16, color: fg, weight: widget.filled ? FontWeight.w700 : FontWeight.w600)),
                if (widget.trailing != null) ...[
                  const SizedBox(width: 8),
                  Icon(widget.trailing, color: fg, size: 20),
                ],
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// A body-group box. Chosen = traced over in highlight chalk.
class ChalkChip extends StatelessWidget {
  const ChalkChip({super.key, required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          height: 48,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: handRadius,
            border: Border.all(color: selected ? c.highlight : c.line, width: selected ? 3 : 2),
          ),
          child: Text(label, style: ink(context, 15.5, color: selected ? c.highlight : c.text, weight: FontWeight.w600)),
        ),
      ),
    );
  }
}

/// Small underlined text you can tap.
class ChalkLink extends StatelessWidget {
  const ChalkLink(this.text, {super.key, required this.onTap});
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(6),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
          child: Text(text,
              style: ink(context, 14, color: context.chalk.muted).copyWith(decoration: TextDecoration.underline)),
        ),
      );
}

/// Today, Tomorrow, Sun 11 ... The chosen day is underlined in highlight chalk.
class DayTabs extends StatelessWidget {
  const DayTabs({super.key, required this.days, required this.selected, required this.labelOf, required this.onPicked});
  final List<DateTime> days;
  final DateTime selected;
  final String Function(DateTime) labelOf;
  final ValueChanged<DateTime> onPicked;

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: days.length,
        separatorBuilder: (_, __) => const SizedBox(width: 18),
        itemBuilder: (context, i) {
          final on = days[i] == selected;
          return GestureDetector(
            onTap: () => onPicked(days[i]),
            child: Container(
              padding: const EdgeInsets.only(top: 6),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: on ? c.highlight : Colors.transparent, width: 3)),
              ),
              child: Text(labelOf(days[i]),
                  style: ink(context, 15, color: on ? c.text : c.muted, weight: on ? FontWeight.w700 : FontWeight.w500)),
            ),
          );
        },
      ),
    );
  }
}
