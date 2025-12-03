import 'package:dio/dio.dart';
import '../models/generation_task.dart';

class SdApiService {
  late final Dio _dio;
  // Android Emulator: 10.0.2.2
  final String baseUrl;

  SdApiService({this.baseUrl = 'http://10.0.2.2:8000'}) {
    // 每次创建新实例时都重新初始化 Dio，避免连接状态问题
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10), // 连接超时
      receiveTimeout: const Duration(seconds: 30),   // 接收超时
      sendTimeout: const Duration(seconds: 30),     // 发送超时
      // 保持连接活跃
      persistentConnection: true,
    ));
  }

  Future<GenerationTask> submitTask({
    required String prompt,
    String? negativePrompt,
  }) async {
    try {
      final response = await _dio.post(
        '/tasks',
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
    } on DioException catch (e) {
      throw _handleDioError(e, '提交任务');
    } catch (e) {
      print('Error submitting task: $e');
      rethrow;
    }
  }

  Future<List<GenerationTask>> getHistory() async {
    try {
      final response = await _dio.get('/tasks');
      
      if (response.statusCode == 200) {
        final List<dynamic> data = response.data;
        return data.map((json) => GenerationTask.fromMap(json)).toList();
      } else {
        throw Exception('Failed to load history: ${response.statusCode}');
      }
    } on DioException catch (e) {
      print('Error loading history: ${_getErrorDescription(e)}');
      return [];
    } catch (e) {
      print('Error loading history: $e');
      return [];
    }
  }

  /// 用于连通性测试，返回详细的诊断信息
  /// 返回: (是否成功, 错误描述)
  Future<({bool success, String message, String? detail})> ping() async {
    try {
      final response = await _dio.get(
        '/tasks',
        options: Options(
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
          validateStatus: (status) => true,
        ),
      );

      if (response.statusCode == 200) {
        return (
          success: true,
          message: '连接成功：服务器可用',
          detail: '状态码: ${response.statusCode}',
        );
      } else {
        return (
          success: false,
          message: '服务器返回错误',
          detail: '状态码: ${response.statusCode}',
        );
      }
    } on DioException catch (e) {
      return (
        success: false,
        message: _getErrorDescription(e),
        detail: _getErrorDetail(e),
      );
    } catch (e) {
      return (
        success: false,
        message: '未知错误',
        detail: e.toString(),
      );
    }
  }

  /// 调用后端 /health，查看 worker / GPU / 模型状态
  Future<({bool success, String message, dynamic data})> health() async {
    try {
      final response = await _dio.get(
        '/health',
        options: Options(
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 10),
          validateStatus: (status) => true,
        ),
      );

      if (response.statusCode == 200) {
        return (
          success: true,
          message: '健康检查成功',
          data: response.data,
        );
      } else {
        return (
          success: false,
          message: '健康检查接口返回异常状态码: ${response.statusCode}',
          data: response.data,
        );
      }
    } on DioException catch (e) {
      return (
        success: false,
        message: _getErrorDescription(e),
        data: _getErrorDetail(e),
      );
    } catch (e) {
      return (
        success: false,
        message: '未知错误: $e',
        data: null,
      );
    }
  }

  /// 处理 DioException 并返回用户友好的错误描述
  String _handleDioError(DioException e, String operation) {
    final description = _getErrorDescription(e);
    throw Exception('$operation 失败: $description');
  }

  /// 获取错误描述（用户友好）
  String _getErrorDescription(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
        return '连接超时：无法连接到服务器';
      case DioExceptionType.sendTimeout:
        return '发送超时：请求发送失败';
      case DioExceptionType.receiveTimeout:
        return '接收超时：服务器响应超时';
      case DioExceptionType.badResponse:
        return '服务器错误：${e.response?.statusCode}';
      case DioExceptionType.cancel:
        return '请求已取消';
      case DioExceptionType.connectionError:
        return '连接错误：无法解析主机或网络不可达';
      case DioExceptionType.badCertificate:
        return '证书错误（HTTPS）';
      case DioExceptionType.unknown:
        final error = e.error;
        if (error is String) {
          if (error.contains('Failed host lookup')) {
            return 'DNS 解析失败：无法找到服务器地址';
          } else if (error.contains('Network is unreachable')) {
            return '网络不可达：请检查网络连接';
          } else if (error.contains('Connection refused')) {
            return '连接被拒绝：服务器可能未运行或端口错误';
          }
        }
        return '未知网络错误：${error ?? e.message}';
    }
  }

  /// 获取详细错误信息（用于诊断）
  String? _getErrorDetail(DioException e) {
    final details = <String>[];
    
    details.add('URL: ${e.requestOptions.uri}');
    
    if (e.response != null) {
      details.add('状态码: ${e.response?.statusCode}');
    }
    
    if (e.message != null && e.message!.isNotEmpty) {
      details.add('消息: ${e.message}');
    }
    
    if (e.error != null) {
      details.add('错误: ${e.error}');
    }
    
    return details.isEmpty ? null : details.join('\n');
  }

  String getImageUrl(String relativePath) {
    if (relativePath.startsWith('http')) return relativePath;
    // 确保路径格式正确
    final cleanPath = relativePath.startsWith('/') 
        ? relativePath.substring(1) 
        : relativePath;
    return '$baseUrl/$cleanPath';
  }

  /// 关闭连接（清理资源）
  void close() {
    _dio.close(force: true);
  }
}
