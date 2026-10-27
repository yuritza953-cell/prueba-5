/**
 * Configuración de autenticación.
 *
 * Puede venir de dos sitios:
 *  1. Variables de compilación de Vite (`VITE_GOOGLE_CLIENT_ID`, ...).
 *  2. Configuración inyectada en runtime por el host (`window.KINORA_AUTH`),
 *     útil en alojamientos estáticos donde no se quiere recompilar.
 *
 * No guardes secretos aquí: Google y Discord se usan como clientes públicos.
 * El client secret de Discord, si algún día se usa, debe vivir solo en el
 * servidor (ver AUTH_SETUP.md).
 */

const runtime =
  typeof window !== 'undefined' && window.KINORA_AUTH && typeof window.KINORA_AUTH === 'object'
    ? window.KINORA_AUTH
    : {};

const env = import.meta.env ?? {};
const base = env.BASE_URL || '/';

const derivedDiscordRedirect =
  typeof window !== 'undefined'
    ? new URL(`${base}auth/discord-callback.html`, window.location.origin).href
    : '';

const clean = value => (typeof value === 'string' ? value.trim() : '');

export const AUTH_CONFIG = Object.freeze({
  googleClientId: clean(runtime.googleClientId) || clean(env.VITE_GOOGLE_CLIENT_ID),
  discordClientId: clean(runtime.discordClientId) || clean(env.VITE_DISCORD_CLIENT_ID),
  discordRedirectUri:
    clean(runtime.discordRedirectUri) ||
    clean(env.VITE_DISCORD_REDIRECT_URI) ||
    derivedDiscordRedirect
});

export const AUTH_PROVIDERS = Object.freeze({
  google: {
    label: 'Google',
    configured: Boolean(AUTH_CONFIG.googleClientId)
  },
  discord: {
    label: 'Discord',
    configured: Boolean(AUTH_CONFIG.discordClientId)
  }
});
