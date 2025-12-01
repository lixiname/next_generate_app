import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Server IP Provider
class ServerIpNotifier extends Notifier<String> {
  static const String _ipKey = 'server_ip';
  static const String _defaultIp = '10.0.2.2:8000'; // Android Emulator default

  @override
  String build() {
    _loadIp();
    return _defaultIp; // Default
  }

  Future<void> _loadIp() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedIp = prefs.getString(_ipKey);
      if (savedIp != null && savedIp.isNotEmpty) {
        state = savedIp;
      }
    } catch (e) {
      print('Error loading server IP: $e');
    }
  }

  Future<void> setIp(String ip) async {
    // 验证IP格式（简单验证，确保包含端口）
    if (ip.isEmpty) {
      return;
    }
    
    // 移除 http:// 或 https:// 前缀（如果有）
    String cleanIp = ip.trim();
    if (cleanIp.startsWith('http://')) {
      cleanIp = cleanIp.substring(7);
    } else if (cleanIp.startsWith('https://')) {
      cleanIp = cleanIp.substring(8);
    }
    
    state = cleanIp;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_ipKey, cleanIp);
    } catch (e) {
      print('Error saving server IP: $e');
    }
  }

  String getBaseUrl() {
    final ip = state;
    if (ip.startsWith('http://') || ip.startsWith('https://')) {
      return ip;
    }
    return 'http://$ip';
  }
}

final serverIpProvider = NotifierProvider<ServerIpNotifier, String>(ServerIpNotifier.new);

