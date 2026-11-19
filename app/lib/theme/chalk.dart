// The "Chalkboard" look: the gym's workout board, written in a clean app font.
//
// Dark mode is chalk on a slate board in a wooden frame.
// Light mode is marker on a whiteboard in an aluminium frame.
// Same layout, same meaning for every colour; only the "board" changes.
//
// Flutter idea used here: a ThemeExtension. ThemeData only has slots for
// standard Material colours, so the board's own colours live in this
// extension and every widget reads them with `context.chalk`.

import 'package:flutter/material.dart';

@immutable
class ChalkColors extends ThemeExtension<ChalkColors> {
  const ChalkColors({
    required this.board,
    required this.frame,
    required this.frameEdge,
    required this.texture,
    required this.text,
    required this.muted,
    required this.line,
    required this.highlight,
    required this.label,
    required this.button,
    required this.buttonInk,
    required this.quiet,
    required this.moderate,
    required this.busy,
  });

  final Color board; // the board itself
  final Color frame; // wooden (dark) or aluminium (light) frame
  final Color frameEdge; // thin line inside the frame
  final String texture; // chalk dust or ghost marks, tiled over the board
  final Color text; // chalk / marker
  final Color muted; // faded, half-rubbed-out writing
  final Color line; // outlines of chips and buttons
  final Color highlight; // circles, the chosen chip, "go" (yellow chalk / red marker)
  final Color label; // section headings (blue chalk / blue marker)
  final Color button; // filled button
  final Color buttonInk; // text on the filled button
  final Color quiet; // tally colours
  final Color moderate;
  final Color busy;

  static const dark = ChalkColors(
    board: Color(0xFF1E2522),
    frame: Color(0xFF6B4A2E),
    frameEdge: Color(0xFF4A321F),
    texture: 'assets/textures/chalk_dust.png',
    text: Color(0xFFECEDE6),
    muted: Color(0x99ECEDE6), // 60%
    line: Color(0x8CECEDE6), // 55%
    highlight: Color(0xFFF2D86A), // yellow chalk
    label: Color(0xFF8EC9F0), // blue chalk
    button: Color(0xFFF2D86A),
    buttonInk: Color(0xFF1E2522),
    quiet: Color(0xFF9BE29B),
    moderate: Color(0xFFF2D86A),
    busy: Color(0xFFF49090),
  );

  static const light = ChalkColors(
    board: Color(0xFFFBFBF8),
    frame: Color(0xFFC9CDD1),
    frameEdge: Color(0xFFA9AEB3),
    texture: 'assets/textures/marker_ghost.png',
    text: Color(0xFF1B1B1B),
    muted: Color(0x8C1B1B1B), // 55%
    line: Color(0x8C1B1B1B),
    highlight: Color(0xFFD63A3A), // red marker
    label: Color(0xFF2A5BD7), // blue marker
    button: Color(0xFF1B1B1B),
    buttonInk: Color(0xFFFBFBF8),
    quiet: Color(0xFF1F9D55),
    moderate: Color(0xFFD99A00),
    busy: Color(0xFFD63A3A),
  );

  @override
  ChalkColors copyWith({Color? highlight}) => ChalkColors(
        board: board,
        frame: frame,
        frameEdge: frameEdge,
        texture: texture,
        text: text,
        muted: muted,
        line: line,
        highlight: highlight ?? this.highlight,
        label: label,
        button: button,
        buttonInk: buttonInk,
        quiet: quiet,
        moderate: moderate,
        busy: busy,
      );

  // Called while the app animates between light and dark: blend every colour.
  @override
  ChalkColors lerp(ThemeExtension<ChalkColors>? other, double t) {
    if (other is! ChalkColors) return this;
    Color m(Color a, Color b) => Color.lerp(a, b, t)!;
    return ChalkColors(
      board: m(board, other.board),
      frame: m(frame, other.frame),
      frameEdge: m(frameEdge, other.frameEdge),
      texture: t < .5 ? texture : other.texture,
      text: m(text, other.text),
      muted: m(muted, other.muted),
      line: m(line, other.line),
      highlight: m(highlight, other.highlight),
      label: m(label, other.label),
      button: m(button, other.button),
      buttonInk: m(buttonInk, other.buttonInk),
      quiet: m(quiet, other.quiet),
      moderate: m(moderate, other.moderate),
      busy: m(busy, other.busy),
    );
  }
}

/// The app's font. null = the phone's own font (SF Pro on iPhone, Roboto on Android),
/// which is what most apps use. Inter is bundled too: set this to 'Inter' to use it.
const String? appFont = null;

/// Text on the board. The chalk feel comes from the board and the drawings;
/// the words stay in a clean app font so they are easy to read.
/// Usage: `ink(context, 16)`, `ink(context, 31, weight: FontWeight.w800)`,
/// `ink(context, 17, digits: true)` for times and counts (all numbers the same width).
TextStyle ink(
  BuildContext context,
  double size, {
  Color? color,
  FontWeight weight = FontWeight.w500,
  TextDecoration? decoration,
  bool digits = false,
}) =>
    TextStyle(
      fontFamily: appFont,
      fontSize: size,
      fontWeight: weight,
      height: 1.25,
      letterSpacing: size >= 28 ? -0.02 * size : 0.0, // big text a little tighter
      color: color ?? context.chalk.text,
      decoration: decoration,
      decorationColor: color ?? context.chalk.muted,
      decorationThickness: 2,
      fontFeatures: digits ? const [FontFeature.tabularFigures()] : null,
    );

/// Lets any widget write `context.chalk.highlight` instead of the long version.
extension ChalkContext on BuildContext {
  ChalkColors get chalk => Theme.of(this).extension<ChalkColors>()!;
}

ThemeData buildChalkTheme(Brightness brightness) {
  final c = brightness == Brightness.dark ? ChalkColors.dark : ChalkColors.light;
  final scheme = ColorScheme.fromSeed(seedColor: c.highlight, brightness: brightness).copyWith(
    primary: c.highlight,
    onPrimary: c.buttonInk,
    surface: c.board,
    onSurface: c.text,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: c.frame,
    fontFamily: appFont,
    extensions: [c],
    textTheme: ThemeData(brightness: brightness).textTheme.apply(
          fontFamily: appFont,
          bodyColor: c.text,
          displayColor: c.text,
        ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: c.text,
      contentTextStyle: TextStyle(fontFamily: appFont, color: c.board, fontSize: 15, fontWeight: FontWeight.w500),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
    bottomSheetTheme: BottomSheetThemeData(backgroundColor: c.board, showDragHandle: true, dragHandleColor: c.muted),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: c.highlight),
  );
}
