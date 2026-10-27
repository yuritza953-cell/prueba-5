import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { AUTH_CONFIG } from './authConfig';

/**
 * Sesión de Kinora basada en proveedores externos.
 *
 * - Google: Google Identity Services (token OAuth) + endpoint userinfo.
 * - Discord: OAuth2 implícito en una ventana emergente y /users/@me.
 *
 * Solo se guarda el perfil público (nombre, correo de Google y avatar).
 * Los access tokens no se persisten: se usan una vez para leer el perfil.
 *
 * Para producción con datos sensibles, valida estos datos en tu backend y
 * emite una sesión propia (ver AUTH_SETUP.md).
 */

const SESSION_KEY = 'kinora:auth-session';
const DISCORD_STATE_KEY = 'kinora:discord-oauth-state';
const GOOGLE_SCRIPT = 'https://accounts.google.com/gsi/client';
const DISCORD_API = 'https://discord.com/api/v10';
const DISCORD_ISSUER = 'https://discord.com';

const AuthContext = createContext({
  user: null,
  provider: null,
  busy: null,
  signInWithGoogle: async () => {},
  signInWithDiscord: async () => {},
  signOut: () => {}
});

const makeError = (code, extra = {}) => {
  const error = new Error(code);
  error.code = code;
  Object.assign(error, extra);
  return error;
};

const readStoredSession = () => {
  try {
    if (typeof window === 'undefined') return null;
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.provider || !parsed.user || !parsed.user.name) return null;
    return parsed;
  } catch {
    return null;
  }
};

const persistSession = session => {
  try {
    if (session) window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else window.localStorage.removeItem(SESSION_KEY);
  } catch {
    /* almacenamiento bloqueado: la sesión vive en memoria */
  }
};

const randomState = () => {
  const bytes = new Uint8Array(24);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
};

let googleScriptPromise = null;

const loadGoogleIdentity = () => {
  if (typeof window === 'undefined') return Promise.reject(makeError('unavailable'));
  if (window.google?.accounts?.oauth2) return Promise.resolve(window.google);
  if (googleScriptPromise) return googleScriptPromise;

  googleScriptPromise = new Promise((resolve, reject) => {
    const fail = () => {
      googleScriptPromise = null;
      // Permite reintentar: un <script> que ya falló no vuelve a emitir load.
      document.querySelector('script[data-kinora-google-identity]')?.remove();
      reject(makeError('google_unavailable'));
    };
    const done = () => {
      if (window.google?.accounts?.oauth2) resolve(window.google);
      else fail();
    };

    const existing = document.querySelector('script[data-kinora-google-identity]');
    if (existing) {
      existing.addEventListener('load', done, { once: true });
      existing.addEventListener('error', fail, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = GOOGLE_SCRIPT;
    script.async = true;
    script.defer = true;
    script.dataset.kinoraGoogleIdentity = 'true';
    script.addEventListener('load', done, { once: true });
    script.addEventListener('error', fail, { once: true });
    document.head.appendChild(script);
  });

  return googleScriptPromise;
};

/**
 * Carga el script de Google antes de pulsar el botón. Al abrir la ventana de
 * login ya se descarga; así `requestAccessToken` se ejecuta dentro del gesto
 * del usuario y el navegador no bloquea la ventana emergente por la espera.
 */
export const preloadGoogleIdentity = () => {
  if (!AUTH_CONFIG.googleClientId) return Promise.resolve(null);
  return loadGoogleIdentity().catch(() => null);
};

const fetchGoogleProfile = async accessToken => {
  const response = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: 'no-store'
  });
  if (!response.ok) throw makeError('profile_failed');
  const data = await response.json();
  return {
    id: data.sub || data.email || 'google-user',
    name: data.name || data.email || 'Google',
    email: data.email || '',
    avatar: data.picture || ''
  };
};

const fetchDiscordProfile = async accessToken => {
  const response = await fetch(`${DISCORD_API}/users/@me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: 'no-store'
  });
  if (!response.ok) throw makeError('profile_failed');
  const data = await response.json();
  const animated = String(data.avatar || '').startsWith('a_');
  const fallbackIndex = Number(data.discriminator || 0) % 5;
  return {
    id: data.id,
    name: data.global_name || data.username || 'Discord',
    email: '',
    avatar: data.avatar
      ? `https://cdn.discordapp.com/avatars/${data.id}/${data.avatar}.${animated ? 'gif' : 'png'}?size=128`
      : `https://cdn.discordapp.com/embed/avatars/${fallbackIndex}.png`
  };
};

export function AuthProvider({ children }) {
  const [session, setSession] = useState(readStoredSession);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    persistSession(session);
  }, [session]);

  const commit = useCallback(profile => {
    const next = {
      v: 1,
      provider: profile.provider,
      user: profile.user,
      createdAt: Date.now()
    };
    setSession(next);
    return next;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!AUTH_CONFIG.googleClientId) throw makeError('missing_config', { provider: 'google' });
    setBusy('google');
    try {
      const google = await loadGoogleIdentity();
      const profile = await new Promise((resolve, reject) => {
        let settled = false;
        const finish = (error, value) => {
          if (settled) return;
          settled = true;
          if (error) reject(error);
          else resolve(value);
        };

        const client = google.accounts.oauth2.initTokenClient({
          client_id: AUTH_CONFIG.googleClientId,
          scope: 'openid email profile',
          callback: async response => {
            if (!response || response.error) {
              finish(makeError('cancelled'));
              return;
            }
            try {
              const user = await fetchGoogleProfile(response.access_token);
              finish(null, user);
            } catch (error) {
              finish(error?.code ? error : makeError('profile_failed'));
            }
          },
          error_callback: error => {
            const type = error?.type || '';
            if (type === 'popup_closed') finish(makeError('cancelled'));
            else if (type === 'popup_failed_to_open') finish(makeError('popup_blocked'));
            else finish(makeError('oauth_failed'));
          }
        });

        try {
          client.requestAccessToken({ prompt: 'select_account' });
        } catch (error) {
          finish(makeError('popup_blocked', { cause: error }));
        }
      });

      return commit({ provider: 'google', user: profile });
    } finally {
      setBusy(null);
    }
  }, [commit]);

  const signInWithDiscord = useCallback(async () => {
    if (!AUTH_CONFIG.discordClientId) throw makeError('missing_config', { provider: 'discord' });
    setBusy('discord');

    try {
      const state = randomState();
      try {
        window.sessionStorage.setItem(DISCORD_STATE_KEY, state);
      } catch {
        /* almacenamiento bloqueado: el state sigue en memoria */
      }

      const params = new URLSearchParams({
        client_id: AUTH_CONFIG.discordClientId,
        response_type: 'token',
        scope: 'identify',
        state,
        redirect_uri: AUTH_CONFIG.discordRedirectUri
      });

      const popup = window.open(
        `https://discord.com/oauth2/authorize?${params.toString()}`,
        'kinora-discord-login',
        'popup=yes,width=520,height=760,menubar=no,toolbar=no,location=yes,status=no'
      );

      if (!popup) throw makeError('popup_blocked');

      const user = await new Promise((resolve, reject) => {
        let settled = false;
        let received = false;

        const storedState = (() => {
          try {
            return window.sessionStorage.getItem(DISCORD_STATE_KEY) || state;
          } catch {
            return state;
          }
        })();

        const clear = () => {
          window.removeEventListener('message', onMessage);
          window.clearInterval(closedPoll);
          window.clearTimeout(timeout);
          try {
            window.sessionStorage.removeItem(DISCORD_STATE_KEY);
          } catch {
            /* ignore */
          }
        };

        const finish = (error, value) => {
          if (settled) return;
          settled = true;
          clear();
          if (error) reject(error);
          else resolve(value);
        };

        async function onMessage(event) {
          if (event.origin !== window.location.origin) return;
          if (event.source !== popup) return;
          if (event.data?.type !== 'kinora:discord-oauth') return;

          received = true;
          const data = event.data;

          if (data.error) {
            finish(makeError(data.error === 'access_denied' ? 'cancelled' : 'oauth_failed'));
            return;
          }
          if (!data.accessToken) {
            finish(makeError('oauth_failed'));
            return;
          }
          if (!data.state || data.state !== storedState) {
            finish(makeError('oauth_failed', { cause: 'state_mismatch' }));
            return;
          }
          if (data.iss && data.iss !== DISCORD_ISSUER) {
            finish(makeError('oauth_failed', { cause: 'issuer_mismatch' }));
            return;
          }

          try {
            const profile = await fetchDiscordProfile(data.accessToken);
            finish(null, profile);
          } catch (error) {
            finish(error?.code ? error : makeError('profile_failed'));
          }
        }

        window.addEventListener('message', onMessage);

        const closedPoll = window.setInterval(() => {
          if (!received && popup.closed) finish(makeError('cancelled'));
        }, 500);

        const timeout = window.setTimeout(() => finish(makeError('timeout')), 5 * 60 * 1000);
      });

      return commit({ provider: 'discord', user });
    } finally {
      setBusy(null);
    }
  }, [commit]);

  const signOut = useCallback(() => {
    setSession(null);
    try {
      window.localStorage.removeItem(SESSION_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({
      user: session?.user ?? null,
      provider: session?.provider ?? null,
      busy,
      signInWithGoogle,
      signInWithDiscord,
      signOut
    }),
    [session, busy, signInWithGoogle, signInWithDiscord, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
