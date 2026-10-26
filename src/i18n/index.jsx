import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import ar from './locales/ar';
import de from './locales/de';
import en from './locales/en';
import es from './locales/es';
import fr from './locales/fr';
import hi from './locales/hi';
import id from './locales/id';
import it from './locales/it';
import ja from './locales/ja';
import ko from './locales/ko';
import pt from './locales/pt';
import ru from './locales/ru';
import tr from './locales/tr';
import vi from './locales/vi';
import zh from './locales/zh';

export const LOCALES = { ar, de, en, es, fr, hi, id, it, ja, ko, pt, ru, tr, vi, zh };
export const LOCALE_CODES = Object.keys(LOCALES);
export const DEFAULT_LOCALE = 'en';

const RTL = new Set(['ar', 'he', 'fa', 'ur']);
const STORAGE_KEY = 'kinora_ui_locale';

const base = tag => String(tag || '').toLowerCase().replace('_', '-').split('-')[0];

/**
 * Normaliza un código de UI/stream (es-MX, pt-BR, en…) al locale de diccionario.
 */
export function resolveLocale(tags) {
  const list = (Array.isArray(tags) ? tags : [tags]).filter(Boolean);
  for (const raw of list) {
    const full = String(raw || '').toLowerCase().replace('_', '-');
    const b = base(full);
    if (b === 'es' && LOCALES.es) return 'es';
    if (b === 'pt' && LOCALES.pt) return 'pt';
    if (LOCALES[b]) return b;
    if (LOCALES[full]) return full;
  }
  return DEFAULT_LOCALE;
}

function detect() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return resolveLocale(saved);
  } catch {
    /* ignore */
  }
  if (typeof navigator === 'undefined') return DEFAULT_LOCALE;
  const tags = navigator.languages?.length ? navigator.languages : [navigator.language];
  return resolveLocale(tags);
}

const read = (dictionary, path) =>
  path.split('.').reduce((node, key) => (node && typeof node === 'object' ? node[key] : undefined), dictionary);

const interpolate = (text, vars) => {
  if (!vars) return text;
  return Object.keys(vars).reduce((out, key) => out.split(`{${key}}`).join(String(vars[key])), text);
};

const I18nContext = createContext({
  locale: 'en',
  dir: 'ltr',
  t: key => key,
  setLocale: () => {}
});

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(detect);
  const dir = RTL.has(locale) ? 'rtl' : 'ltr';

  const setLocale = useCallback(code => {
    const next = resolveLocale(code);
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
    document.documentElement.dataset.locale = locale;
  }, [locale, dir]);

  const value = useMemo(() => {
    const dictionary = LOCALES[locale] ?? LOCALES[DEFAULT_LOCALE];
    const t = (key, vars) => {
      const value = read(dictionary, key);
      if (typeof value === 'string') return interpolate(value, vars);
      const fallback = read(LOCALES[DEFAULT_LOCALE], key);
      return typeof fallback === 'string' ? interpolate(fallback, vars) : key;
    };
    return { locale, dir, t, setLocale };
  }, [locale, dir, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);

export const useT = () => useContext(I18nContext).t;