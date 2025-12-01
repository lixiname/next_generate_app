import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';
import '../models/generation_task.dart';
import '../providers/app_providers.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  // Store notifier reference to avoid accessing ref in deactivate
  dynamic _historyNotifier;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _historyNotifier = ref.read(historyProvider.notifier);
        _historyNotifier.startPolling();
      }
    });
  }

  @override
  void deactivate() {
    // Use stored notifier reference instead of ref.read
    // This avoids accessing ref when widget lifecycle is defunct
    if (_historyNotifier != null) {
      try {
        _historyNotifier.stopPolling();
      } catch (e) {
        // Silently handle if notifier is no longer available
        print('Error stopping polling: $e');
      }
    }
    super.deactivate();
  }

  @override
  Widget build(BuildContext context) {
    final history = ref.watch(historyProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(historyProvider.notifier).refresh();
            },
          ),
        ],
      ),
      body: history.isEmpty
          ? const Center(child: Text('No history yet.'))
          : MasonryGridView.count(
              padding: const EdgeInsets.all(12),
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              itemCount: history.length,
              itemBuilder: (context, index) {
                final task = history[index];
                return TaskCard(task: task);
              },
            ),
    );
  }
}

class TaskCard extends ConsumerWidget {
  final GenerationTask task;

  const TaskCard({super.key, required this.task});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final apiService = ref.read(sdApiServiceProvider);
    final theme = Theme.of(context);

    return GestureDetector(
      onTap: () {
        context.push('/image/${task.id}', extra: task);
      },
      child: Card(
        elevation: 2,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image Section with Hero Animation
            AspectRatio(
              aspectRatio: 1.0, // Square aspect ratio for now, can be dynamic
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Hero(
                    tag: 'image-${task.id}',
                    child: _buildImage(task, apiService),
                  ),
                  if (task.status != TaskStatus.completed)
                    Container(
                      color: Colors.black45,
                      child: Center(child: _buildStatusIndicator(task)),
                    ),
                ],
              ),
            ),
            
            // Info Section
            Padding(
              padding: const EdgeInsets.all(10.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    task.prompt,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        DateFormat.jm().format(task.timestamp),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: Colors.grey[600],
                        ),
                      ),
                      if (task.status == TaskStatus.completed)
                         Icon(Icons.check_circle, size: 14, color: Colors.green[400])
                      else if (task.status == TaskStatus.failed)
                         Icon(Icons.error, size: 14, color: Colors.red[400])
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImage(GenerationTask task, dynamic apiService) {
    if (task.status == TaskStatus.completed && task.imageUrl != null) {
      return CachedNetworkImage(
        imageUrl: apiService.getImageUrl(task.imageUrl!),
        fit: BoxFit.cover,
        placeholder: (context, url) => Container(color: Colors.grey[300]),
        errorWidget: (context, url, error) => const Icon(Icons.broken_image),
      );
    }
    return Container(color: Colors.grey[200]);
  }

  Widget _buildStatusIndicator(GenerationTask task) {
    if (task.status == TaskStatus.processing) {
      return const CircularProgressIndicator(color: Colors.white);
    } else if (task.status == TaskStatus.submitted) {
      return const Icon(Icons.hourglass_empty, color: Colors.white70, size: 32);
    } else if (task.status == TaskStatus.failed) {
      return const Icon(Icons.error_outline, color: Colors.redAccent, size: 32);
    }
    return const SizedBox.shrink();
  }
}
