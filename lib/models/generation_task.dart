import 'dart:convert';

enum TaskStatus {
  submitted,
  processing,
  completed,
  failed,
}

class GenerationTask {
  final String id;
  final String prompt;
  final String? negativePrompt;
  final DateTime timestamp;
  final TaskStatus status;
  final String? imageUrl;

  GenerationTask({
    required this.id,
    required this.prompt,
    this.negativePrompt,
    required this.timestamp,
    required this.status,
    this.imageUrl,
  });

  GenerationTask copyWith({
    String? id,
    String? prompt,
    String? negativePrompt,
    DateTime? timestamp,
    TaskStatus? status,
    String? imageUrl,
  }) {
    return GenerationTask(
      id: id ?? this.id,
      prompt: prompt ?? this.prompt,
      negativePrompt: negativePrompt ?? this.negativePrompt,
      timestamp: timestamp ?? this.timestamp,
      status: status ?? this.status,
      imageUrl: imageUrl ?? this.imageUrl,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'prompt': prompt,
      'negative_prompt': negativePrompt, // Updated to match backend
      'created_at': timestamp.toIso8601String(), // Updated to match backend
      'status': status.name,
      'imageUrl': imageUrl,
    };
  }

  factory GenerationTask.fromMap(Map<String, dynamic> map) {
    return GenerationTask(
      id: map['id'],
      prompt: map['prompt'],
      // Backend uses snake_case 'negative_prompt'
      negativePrompt: map['negative_prompt'] ?? map['negativePrompt'],
      // Backend uses 'created_at'
      timestamp: DateTime.parse(map['created_at'] ?? map['timestamp']),
      status: TaskStatus.values.firstWhere(
        (e) => e.name == map['status'],
        orElse: () => TaskStatus.failed,
      ),
      imageUrl: map['imageUrl'],
    );
  }

  String toJson() => json.encode(toMap());

  factory GenerationTask.fromJson(String source) =>
      GenerationTask.fromMap(json.decode(source));
}
