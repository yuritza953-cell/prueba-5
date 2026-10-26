/** Idiomas de audio con cadena de stream resolve propia. */
export const STREAM_LANG_CODES = ['es-MX', 'es-ES', 'en', 'fr', 'pt-BR'];

export const AUDIO_LANGS = [
  { code: 'es-MX', labelKey: 'player.langEsMx' },
  { code: 'es-ES', labelKey: 'player.langEsEs' },
  { code: 'en', labelKey: 'player.langEn' },
  { code: 'fr', labelKey: 'player.langFr' },
  { code: 'pt-BR', labelKey: 'player.langPtBr' },
];

/**
 * Idiomas del selector de la barra de búsqueda (UI + preferencia de audio).
 * Los que no tienen cadena de stream resuelven en inglés (ver streamLangFor).
 */
export const UI_LANG_OPTIONS = [
  { key: 'es-MX', name: 'Español (Latino)', short: 'Latino' },
  { key: 'es-ES', name: 'Español (Castellano)', short: 'Castellano' },
  { key: 'en', name: 'English', short: 'EN' },
  { key: 'pt-BR', name: 'Português (Brasil)', short: 'PT' },
  { key: 'fr', name: 'Français', short: 'FR' },
  { key: 'de', name: 'Deutsch', short: 'DE' },
  { key: 'it', name: 'Italiano', short: 'IT' },
  { key: 'ru', name: 'Русский', short: 'RU' },
  { key: 'ja', name: '日本語', short: 'JA' },
  { key: 'ko', name: '한국어', short: 'KO' },
  { key: 'zh', name: '中文', short: 'ZH' },
  { key: 'ar', name: 'العربية', short: 'AR' },
  { key: 'hi', name: 'हिन्दी', short: 'HI' },
  { key: 'tr', name: 'Türkçe', short: 'TR' },
  { key: 'id', name: 'Bahasa Indonesia', short: 'ID' },
  { key: 'vi', name: 'Tiếng Việt', short: 'VI' },
];

export function normalizeAudioLang(lang) {
  const s = String(lang || 'es-MX').toLowerCase().replace('_', '-');
  if (['es-mx', 'es-419', 'es-lat', 'es-la', 'latino', 'lat', 'es'].includes(s)) return 'es-MX';
  if (['es-es', 'castellano', 'spain'].includes(s)) return 'es-ES';
  if (s.startsWith('en')) return 'en';
  if (s.startsWith('fr')) return 'fr';
  if (s.startsWith('pt')) return 'pt-BR';
  return s;
}

/** Idioma de stream: si no hay cadena, inglés. */
export function streamLangFor(uiLang) {
  const code = normalizeAudioLang(uiLang);
  if (STREAM_LANG_CODES.includes(code)) return code;
  // es genérico → latino
  if (String(code).startsWith('es')) return 'es-MX';
  if (String(code).startsWith('pt')) return 'pt-BR';
  if (String(code).startsWith('fr')) return 'fr';
  return 'en';
}

export function labelForLang(code, t) {
  const row = AUDIO_LANGS.find(x => x.code === code);
  if (row) {
    try {
      return t(row.labelKey);
    } catch {
      /* fallthrough */
    }
  }
  const ui = UI_LANG_OPTIONS.find(x => x.key === code);
  return ui?.name || code;
}