import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:just_audio/just_audio.dart';
import 'package:readle/features/reader/services/audio_service.dart';

class FakeFlutterTts extends FlutterTts {
  String? lastSpokenText;
  double? lastRate;
  String? lastLanguage;
  bool wasStopped = false;

  @override
  Future<dynamic> setLanguage(String language) async {
    lastLanguage = language;
    return 1;
  }

  @override
  Future<dynamic> setSpeechRate(double rate) async {
    lastRate = rate;
    return 1;
  }

  @override
  Future<dynamic> speak(String text, {bool focus = false}) async {
    lastSpokenText = text;
    return 1;
  }

  @override
  Future<dynamic> stop() async {
    wasStopped = true;
    return 1;
  }
}

class FakeAudioPlayer implements AudioPlayer {
  String? lastUrl;
  double? lastSpeed;
  bool failOnPlay = false;
  bool wasStopped = false;

  @override
  bool get playing => false;

  @override
  Future<void> setSpeed(double speed) async {
    lastSpeed = speed;
  }

  @override
  Future<Duration?> setUrl(
    String url, {
    Map<String, String>? headers,
    Duration? initialPosition,
    Duration? initialIndex,
    bool preload = true,
    dynamic tag,
  }) async {
    lastUrl = url;
    if (failOnPlay) {
      throw Exception('Network error');
    }
    return Duration.zero;
  }

  @override
  Future<void> play() async {
    if (failOnPlay) {
      throw Exception('Play error');
    }
  }

  @override
  Future<void> stop() async {
    wasStopped = true;
  }

  @override
  Future<void> dispose() async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AppAudioService Unit Tests (FE-04b / AC-6)', () {
    late FakeFlutterTts fakeTts;
    late FakeAudioPlayer fakePlayer;
    late AppAudioService audioService;

    setUp(() {
      fakeTts = FakeFlutterTts();
      fakePlayer = FakeAudioPlayer();
      audioService = AppAudioService(tts: fakeTts, player: fakePlayer);
    });

    test('speak adjusts speech rate by 0.5 * speed', () async {
      await audioService.speak('hello', speed: 1.0);
      expect(fakeTts.lastLanguage, equals('en-US'));
      expect(fakeTts.lastRate, equals(0.5));
      expect(fakeTts.lastSpokenText, equals('hello'));

      await audioService.speak('hello slow', speed: 0.75);
      expect(fakeTts.lastRate, equals(0.375));
      expect(fakeTts.lastSpokenText, equals('hello slow'));
    });

    test('playUrl sets speed on player and plays url successfully', () async {
      await audioService.playUrl('https://example.com/audio.mp3', speed: 0.75);
      expect(fakePlayer.lastSpeed, equals(0.75));
      expect(fakePlayer.lastUrl, equals('https://example.com/audio.mp3'));
      expect(fakeTts.lastSpokenText, isNull);
    });

    test('playUrl falls back to speak when player fails', () async {
      fakePlayer.failOnPlay = true;
      await audioService.playUrl(
        'https://broken.url/fail.mp3',
        speed: 0.75,
        fallbackText: 'fallback phrase',
      );

      // Verify fallback was triggered with matching speed
      expect(fakeTts.lastSpokenText, equals('fallback phrase'));
      expect(fakeTts.lastRate, equals(0.375));
    });

    test('buildAudioPlayedPayload formats correctly', () {
      final p1 = buildAudioPlayedPayload(source: AudioEventSource.item, speed: 0.75);
      expect(p1, {'source': 'item', 'speed': 0.75});

      final p2 = buildAudioPlayedPayload(source: AudioEventSource.wordRow, speed: 1.0);
      expect(p2, {'source': 'word_row', 'speed': 1.0});

      final p3 = buildAudioPlayedPayload(source: AudioEventSource.tooltip, speed: 1.0);
      expect(p3, {'source': 'tooltip', 'speed': 1.0});
    });
  });
}
