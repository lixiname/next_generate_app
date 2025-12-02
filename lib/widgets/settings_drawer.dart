import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/theme_provider.dart';
import '../providers/server_ip_provider.dart';
import '../providers/app_providers.dart';

class SettingsDrawer extends ConsumerWidget {
  const SettingsDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentTheme = ref.watch(themeProvider);
    final theme = Theme.of(context);

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(
              color: theme.colorScheme.primary,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.settings,
                  size: 48,
                  color: theme.colorScheme.onPrimary,
                ),
                const SizedBox(height: 8),
                Text(
                  'Settings',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    color: theme.colorScheme.onPrimary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Theme Color',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: ThemeColor.values.map((themeColor) {
                    final isSelected = currentTheme == themeColor;
                    return GestureDetector(
                      onTap: () {
                        ref.read(themeProvider.notifier).setTheme(themeColor);
                      },
                      child: Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: themeColor.color,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isSelected
                                ? theme.colorScheme.primary
                                : Colors.transparent,
                            width: 3,
                          ),
                          boxShadow: isSelected
                              ? [
                                  BoxShadow(
                                    color: themeColor.color.withValues(alpha: 0.5),
                                    blurRadius: 8,
                                    spreadRadius: 2,
                                  ),
                                ]
                              : null,
                        ),
                        child: isSelected
                            ? Icon(
                                Icons.check,
                                color: Colors.white,
                                size: 28,
                              )
                            : null,
                      ),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 8),
                Text(
                  'Selected: ${currentTheme.name}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Server Settings',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                _ServerIpInput(theme: theme),
              ],
            ),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('About'),
            subtitle: const Text('Next Generate App'),
            onTap: () {
              Navigator.pop(context);
              showAboutDialog(
                context: context,
                applicationName: 'Next Generate App',
                applicationVersion: '1.0.0',
                applicationIcon: const Icon(Icons.auto_awesome, size: 48),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _ServerIpInput extends ConsumerStatefulWidget {
  final ThemeData theme;
  
  const _ServerIpInput({required this.theme});

  @override
  ConsumerState<_ServerIpInput> createState() => _ServerIpInputState();
}

class _ServerIpInputState extends ConsumerState<_ServerIpInput> {
  late TextEditingController _ipController;
  bool _isInitialized = false;

  @override
  void initState() {
    super.initState();
    _ipController = TextEditingController();
  }

  @override
  void dispose() {
    _ipController.dispose();
    super.dispose();
  }

  void _updateControllerIfNeeded(String currentIp) {
    if (!_isInitialized || _ipController.text != currentIp) {
      _ipController.text = currentIp;
      _isInitialized = true;
    }
  }

  Future<void> _saveIp() async {
    final value = _ipController.text.trim();
    if (value.isEmpty) return;

    // 先保存 IP 配置（这会触发 Provider 重建）
    await ref.read(serverIpProvider.notifier).setIp(value);

    // 显示测试中提示
    final testSnackBar = ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Row(
          children: [
            SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 12),
            Expanded(child: Text('正在测试与服务器的连接...')),
          ],
        ),
        duration: Duration(seconds: 10),
      ),
    );

    try {
      // 等待一小段时间，确保 Provider 已重建
      await Future.delayed(const Duration(milliseconds: 100));
      
      // 使用新的 SdApiService 实例测试连接
      final api = ref.read(sdApiServiceProvider);
      final result = await api.ping();

      // 关闭测试中的提示
      testSnackBar.close();

      // 显示详细结果
      if (result.success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  result.message,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                if (result.detail != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    result.detail!,
                    style: const TextStyle(fontSize: 12),
                  ),
                ],
              ],
            ),
            backgroundColor: Colors.green,
            duration: const Duration(seconds: 4),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  result.message,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                if (result.detail != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    result.detail!,
                    style: const TextStyle(fontSize: 12),
                  ),
                ],
                const SizedBox(height: 8),
                const Text(
                  '💡 提示：检查 IP/端口、防火墙设置、服务器是否运行',
                  style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic),
                ),
              ],
            ),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 6),
            action: SnackBarAction(
              label: '查看详情',
              textColor: Colors.white,
              onPressed: () {
                // 可以在这里显示一个对话框显示完整错误信息
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('连接诊断信息'),
                    content: SingleChildScrollView(
                      child: Text(
                        '错误：${result.message}\n\n'
                        '${result.detail ?? "无详细信息"}',
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('关闭'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        );
      }
    } catch (e) {
      testSnackBar.close();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('测试连接时发生异常: $e'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 5),
        ),
      );
    }

    FocusScope.of(context).unfocus();
  }

  @override
  Widget build(BuildContext context) {
    final currentIp = ref.watch(serverIpProvider);
    _updateControllerIfNeeded(currentIp);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _ipController,
          decoration: InputDecoration(
            labelText: 'Server IP:Port',
            hintText: '例如: 192.168.1.100:8000',
            helperText: '同一WiFi下的Windows服务器IP',
            border: const OutlineInputBorder(),
            prefixIcon: const Icon(Icons.dns),
            suffixIcon: IconButton(
              icon: const Icon(Icons.clear),
              onPressed: () {
                _ipController.clear();
              },
            ),
          ),
          keyboardType: TextInputType.url,
          inputFormatters: [
            FilteringTextInputFormatter.allow(
              RegExp(r'[0-9.:]'),
            ),
          ],
          onSubmitted: (_) => _saveIp(),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(
              child: Text(
                '当前: $currentIp',
                style: widget.theme.textTheme.bodySmall?.copyWith(
                  color: Colors.grey[600],
                ),
              ),
            ),
            TextButton.icon(
              onPressed: _saveIp,
              icon: const Icon(Icons.save, size: 18),
              label: const Text('保存'),
            ),
          ],
        ),
      ],
    );
  }
}

