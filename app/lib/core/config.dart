class AppConfig {
  static const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');
  static const useFixture = bool.fromEnvironment('USE_FIXTURE', defaultValue: true);

  static bool get hasSupabaseConfig =>
      supabaseUrl.trim().isNotEmpty && supabaseAnonKey.trim().isNotEmpty;

  static bool get useSupabase => hasSupabaseConfig && !useFixture;
  static bool get shouldInitializeSupabase => useSupabase;

  static bool supabaseReady = false;
  static bool get isSupabaseInitialized => supabaseReady;
  static set isSupabaseInitialized(bool val) => supabaseReady = val;
}

