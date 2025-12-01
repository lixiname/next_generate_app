import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/generation_task.dart';
import '../providers/app_providers.dart';

class ImageViewScreen extends ConsumerWidget {
  final GenerationTask task;

  const ImageViewScreen({super.key, required this.task});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final apiService = ref.read(sdApiServiceProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Image View'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
      ),
      body: Center(
        child: Hero(
          tag: 'image-${task.id}',
          child: _buildContent(apiService),
        ),
      ),
    );
  }

  Widget _buildContent(dynamic apiService) {
    if (task.status == TaskStatus.completed && task.imageUrl != null) {
      return InteractiveViewer(
        child: CachedNetworkImage(
          imageUrl: apiService.getImageUrl(task.imageUrl!),
          fit: BoxFit.contain,
          width: double.infinity,
          height: double.infinity,
          placeholder: (context, url) => const Center(child: CircularProgressIndicator(color: Colors.white)),
          errorWidget: (context, url, error) {
             return Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.broken_image, size: 64, color: Colors.grey),
                const SizedBox(height: 16),
                const Text('Failed to load image', style: TextStyle(color: Colors.white)),
                Text(task.imageUrl ?? '', style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ],
            );
          },
        ),
      );
    } else if (task.status == TaskStatus.failed) {
      return const Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: Colors.red),
          SizedBox(height: 16),
          Text('Generation Failed', style: TextStyle(color: Colors.white)),
        ],
      );
    } else {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(color: Colors.white),
          const SizedBox(height: 16),
          Text('Status: ${task.status.name}', style: const TextStyle(color: Colors.white)),
        ],
      );
    }
  }
}
