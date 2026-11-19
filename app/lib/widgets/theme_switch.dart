// The Auto / Light / Dark switch in the top corner.
// Flutter ideas: a ValueNotifier holds app-wide state; ValueListenableBuilder
// rebuilds only the widgets that care when it changes.

import 'package:flutter/material.dart';

import '../theme/chalk.dart';

/// The whole app listens to this (see main.dart). Auto = follow the phone.
final themeMode = ValueNotifier<ThemeMode>(ThemeMode.system);

class ThemeSwitch extends StatelessWidget {
  const ThemeSwitch({super.key});

  static const _order = [ThemeMode.system, ThemeMode.light, ThemeMode.dark];

  @override
  Widget build(BuildContext context) {
    final c = context.chalk;
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: themeMode,
      builder: (context, mode, _) {
        final (icon, label) = switch (mode) {
          ThemeMode.light => (Icons.light_mode_outlined, 'whiteboard'),
          ThemeMode.dark => (Icons.dark_mode_outlined, 'chalkboard'),
          _ => (Icons.brightness_auto_outlined, 'auto'),
        };
        return TextButton.icon(
          onPressed: () => themeMode.value = _order[(_order.indexOf(mode) + 1) % _order.length],
          icon: Icon(icon, size: 18, color: c.muted),
          label: Text(label, style: ink(context, 13, color: c.muted)),
          style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 8)),
        );
      },
    );
  }
}
