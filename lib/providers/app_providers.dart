import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/sd_api_service.dart';
import '../models/generation_task.dart';
import 'server_ip_provider.dart';

// No longer need storage service for history source of truth, 
// but might keep it if we want offline capability later. 
// For now, removing it to simplify and align with backend.

final sdApiServiceProvider = Provider((ref) {
  // Watch serverIpProvider to rebuild when IP changes
  ref.watch(serverIpProvider); // This ensures the provider rebuilds when IP changes
  final baseUrl = ref.read(serverIpProvider.notifier).getBaseUrl();
  return SdApiService(baseUrl: baseUrl);
});

class HistoryNotifier extends Notifier<List<GenerationTask>> {
  late final SdApiService _apiService;
  Timer? _pollingTimer;

  @override
  List<GenerationTask> build() {
    _apiService = ref.watch(sdApiServiceProvider);
    
    // Load initial history
    Future.microtask(() => _loadHistory());
    
    ref.onDispose(() {
      _pollingTimer?.cancel();
    });
    
    return [];
  }

  Future<void> _loadHistory() async {
    final history = await _apiService.getHistory();
    state = history;
  }

  Future<void> createTask(String prompt, String? negativePrompt) async {
    try {
      final newTask = await _apiService.submitTask(
        prompt: prompt,
        negativePrompt: negativePrompt,
      );
      
      // Add to top of list
      state = [newTask, ...state];
    } catch (e) {
      print('Failed to create task: $e');
      // Optionally set error state
    }
  }
  
  void startPolling() {
    if (_pollingTimer != null && _pollingTimer!.isActive) return;
    
    // Load immediately when starting polling
    _loadHistory();
    
    _pollingTimer = Timer.periodic(const Duration(minutes: 1), (timer) async {
      // Check if there are any non-terminal tasks
      final hasActiveTasks = state.any((t) => 
        t.status == TaskStatus.submitted || t.status == TaskStatus.processing);
      
      if (hasActiveTasks) {
        // Simple strategy: Reload all history to get updates
        // Ideally: Poll specific tasks or use WebSocket
        await _loadHistory();
      }
    });
  }
  
  void stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
  }
  
  Future<void> refresh() async {
    await _loadHistory();
  }
}

final historyProvider = NotifierProvider<HistoryNotifier, List<GenerationTask>>(HistoryNotifier.new);
