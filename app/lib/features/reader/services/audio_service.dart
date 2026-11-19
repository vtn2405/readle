import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:just_audio/just_audio.dart';

enum AudioEventSource {
  item('item'),
  wordRow('word_row'),
  tooltip('tooltip');

  final String value;
  const AudioEventSource(this.value);
}

Map<String, dynamic> buildAudioPlayedPayload({
  required AudioEventSource source,
  required double speed,
}) =>
    {
      'source': source.value,
      'speed': speed,
    };

abstract class AudioService {
  Future<void> speak(String text, {double speed = 1.0});
  Future<void> playUrl(String url, {double speed = 1.0, String? fallbackText});
  Future<void> stop();
  void dispose();
}

class AppAudioService implements AudioService {
  final FlutterTts _tts;
  final AudioPlayer _player;
  bool _ttsInitialized = false;

  AppAudioService({
    FlutterTts? tts,
    AudioPlayer? player,
  })  : _tts = tts ?? FlutterTts(),
        _player = player ?? AudioPlayer();

  Future<void> _initTts() async {
    if (!_ttsInitialized) {
      try {
        await _tts.setLanguage('en-US');
        _ttsInitialized = true;
      } catch (e) {
        debugPrint('Lỗi khởi tạo TTS: $e');
      }
    }
  }

  @override
  Future<void> speak(String text, {double speed = 1.0}) async {
    try {
      await stop();
      await _initTts();
      // Base speech rate là 0.5; với speed 0.75 -> 0.5 * 0.75 = 0.375
      await _tts.setSpeechRate(0.5 * speed);
      await _tts.speak(text);
    } catch (e) {
      debugPrint('Lỗi speak TTS: $e');
    }
  }

  @override
  Future<void> playUrl(
    String url, {
    double speed = 1.0,
    String? fallbackText,
  }) async {
    try {
      await stop();
      await _player.setSpeed(speed);
      await _player.setUrl(url);
      await _player.play();
    } catch (e) {
      debugPrint('Lỗi play audio URL: $e');
      if (fallbackText != null && fallbackText.isNotEmpty) {
        await speak(fallbackText, speed: speed);
      }
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _tts.stop();
      if (_player.playing) {
        await _player.stop();
      }
    } catch (e) {
      debugPrint('Lỗi stop audio: $e');
    }
  }

  @override
  void dispose() {
    _tts.stop();
    _player.dispose();
  }
}

final audioServiceProvider = Provider<AudioService>((ref) {
  final service = AppAudioService();
  ref.onDispose(() => service.dispose());
  return service;
});

double toggleSpeed(double s) => s == 1.0 ? 0.75 : 1.0;

final speedModeProvider = StateProvider<double>((ref) => 1.0);

