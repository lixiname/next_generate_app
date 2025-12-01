import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Theme color options
enum ThemeColor {
  blue(Colors.blue, 'Blue'),
  purple(Colors.purple, 'Purple'),
  green(Colors.green, 'Green'),
  orange(Colors.orange, 'Orange'),
  pink(Colors.pink, 'Pink'),
  teal(Colors.teal, 'Teal'),
  indigo(Colors.indigo, 'Indigo'),
  red(Colors.red, 'Red');

  final Color color;
  final String name;
  const ThemeColor(this.color, this.name);
}

// Theme Provider
class ThemeNotifier extends Notifier<ThemeColor> {
  static const String _themeKey = 'theme_color';

  @override
  ThemeColor build() {
    _loadTheme();
    return ThemeColor.blue; // Default
  }

  Future<void> _loadTheme() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final themeIndex = prefs.getInt(_themeKey) ?? 0;
      if (themeIndex >= 0 && themeIndex < ThemeColor.values.length) {
        state = ThemeColor.values[themeIndex];
      }
    } catch (e) {
      print('Error loading theme: $e');
    }
  }

  Future<void> setTheme(ThemeColor theme) async {
    state = theme;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_themeKey, theme.index);
    } catch (e) {
      print('Error saving theme: $e');
    }
  }
}

final themeProvider = NotifierProvider<ThemeNotifier, ThemeColor>(ThemeNotifier.new);

