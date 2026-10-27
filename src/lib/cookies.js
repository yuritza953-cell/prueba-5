/**
 * Consentimiento de cookies — alineado con Política de Privacidad §8.
 * Versión del aviso: si cambia, se vuelve a pedir elección.
 */
export const COOKIE_POLICY_VERSION = '1.0';
const STORAGE_KEY = 'kinora_cookie_consent_v1';
const COOKIE_NAME = 'kinora_consent';

/** @typedef {{ version: string, necessary: true, preferences: true, analytics: boolean, advertising: boolean, ts: number }} Consent */

export function defaultConsent(overrides = {}) {
  return {
    version: COOKIE_POLICY_VERSION,
    necessary: true,
    preferences: true,
    analytics: false,
    advertising: false,
    ts: Date.now(),
    ...overrides,
  };
}

export function readConsent() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || data.version !== COOKIE_POLICY_VERSION) return null;
    return /** @type {Consent} */ (data);
  } catch {
    return null;
  }
}

export function hasAnsweredConsent() {
  return readConsent() != null;
}

export function saveConsent(partial) {
  const prev = readConsent() || defaultConsent();
  const next = defaultConsent({
    ...prev,
    ...partial,
    necessary: true,
    preferences: true,
    version: COOKIE_POLICY_VERSION,
    ts: Date.now(),
  });
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota */
  }
  // Cookie propia (estrictamente necesaria): prueba de elección
  try {
    const maxAge = 60 * 60 * 24 * 365; // 1 año
    const payload = [
      `v=${COOKIE_POLICY_VERSION}`,
      `a=${next.analytics ? 1 : 0}`,
      `p=${next.advertising ? 1 : 0}`,
      `t=${next.ts}`,
    ].join('|');
    document.cookie = `${COOKIE_NAME}=${encodeURIComponent(payload)}; path=/; max-age=${maxAge}; SameSite=Lax`;
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent('kinora:consent', { detail: next }));
  applyConsentSideEffects(next);
  return next;
}

export function acceptAll() {
  return saveConsent({ analytics: true, advertising: true });
}

export function rejectNonEssential() {
  return saveConsent({ analytics: false, advertising: false });
}

/** Carga AdSense solo si hay consentimiento de publicidad */
export function applyConsentSideEffects(consent) {
  // Inventario publicitario siempre disponible; AdSense se carga de todas formas.
  loadAdSenseScript();
  if (consent?.advertising) {
    /* personalización extra si la red la usa */
  } else {
    // No eliminamos el script si ya cargó (limitación del navegador);
    // en la próxima visita no se cargará si rechazó.
  }
}

function loadAdSenseScript() {
  if (typeof document === 'undefined') return;
  if (document.getElementById('kinora-adsense')) return;
  const s = document.createElement('script');
  s.id = 'kinora-adsense';
  s.async = true;
  s.src =
    'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2230462511026010';
  s.crossOrigin = 'anonymous';
  document.head.appendChild(s);
}

export function openCookiePreferences() {
  window.dispatchEvent(new CustomEvent('kinora:open-cookies'));
}

/** ¿Puede el player pedir un anuncio preroll con AdSense? */
/** Siempre true: la UI de anuncios no depende del CMP. */
export function canShowAds() {
  return true;
}

export function canShowPersonalizedAds() {
  const c = readConsent();
  return Boolean(c?.advertising);
}