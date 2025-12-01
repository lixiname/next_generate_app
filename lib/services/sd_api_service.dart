import 'package:dio/dio.dart';
import '../models/generation_task.dart';

class SdApiService {
  final Dio _dio = Dio();
  // Android Emulator: 10.0.2.2
  final String baseUrl;

  SdApiService({this.baseUrl = 'http://10.0.2.2:8000'});

  Future<GenerationTask> submitTask({
    required String prompt,
    String? negativePrompt,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/tasks',
        data: {
          "prompt": prompt,
          "negative_prompt": negativePrompt,
        },
      );
      
      if (response.statusCode == 200) {
        return GenerationTask.fromMap(response.data);
      } else {
        throw Exception('Failed to submit task: ${response.statusCode}');
      }
    } catch (e) {
      print('Error submitting task: $e');
      rethrow;
    }
  }

  Future<List<GenerationTask>> getHistory() async {
    try {
      final response = await _dio.get('$baseUrl/tasks');
      
      if (response.statusCode == 200) {
        final List<dynamic> data = response.data;
        return data.map((json) => GenerationTask.fromMap(json)).toList();
      } else {
        throw Exception('Failed to load history: ${response.statusCode}');
      }
    } catch (e) {
      print('Error loading history: $e');
      return [];
    }
  }

  /// 用于简单连通性测试：
  /// - 请求 /tasks
  /// - 只在返回 200 时视为成功
  /// - 任何网络错误 / 超时 / 非 200 状态码都会抛异常
  Future<void> ping() async {
    try {
      final response = await _dio.get(
        '$baseUrl/tasks',
        options: Options(
          sendTimeout: const Duration(seconds: 3),
          receiveTimeout: const Duration(seconds: 3),
          // 不要在这里抛错，交给下面手动判断
          validateStatus: (status) => true,
        ),
      );

      if (response.statusCode != 200) {
        throw Exception('Ping failed: ${response.statusCode}');
      }
    } catch (e) {
      print('Ping error: $e');
      rethrow;
    }
  }

  String getImageUrl(String relativePath) {
    if (relativePath.startsWith('http')) return relativePath;
    return '$baseUrl/$relativePath';
  }
}
