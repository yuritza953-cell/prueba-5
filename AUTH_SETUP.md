# Inicio de sesión con Google y Discord

La web ya tiene el botón **Iniciar sesión**, la ventana con los dos proveedores,
el avatar circular, el menú de cuenta y el cierre de sesión.

Para que los botones funcionen solo faltan las credenciales de cada proveedor.
No hay que tocar los componentes: se leen de variables de entorno o de una
configuración de runtime.

## 1. Cómo funciona

| Proveedor | Flujo | Datos que se guardan |
| --- | --- | --- |
| Google | Google Identity Services + `userinfo` | nombre, correo y foto |
| Discord | OAuth2 implícito en ventana emergente + `/users/@me` | nombre y foto |

La sesión se guarda en `localStorage` con la clave `kinora:auth-session`.
**No se guardan access tokens**: se usan una sola vez para leer el perfil.
El botón de cerrar sesión elimina esa clave.

Archivos principales:

- `src/lib/auth.jsx`: lógica de Google/Discord y estado de la sesión.
- `src/lib/authConfig.js`: lectura de variables y configuración de runtime.
- `src/components/AccountButton.jsx`: botón, ventana de login y menú de cuenta.
- `public/auth/discord-callback.html`: página que recibe la respuesta de Discord.
- `.env.example`: plantilla de variables.

El login está traducido en los **15 idiomas** de la interfaz (`ar`, `de`, `en`,
`es`, `fr`, `hi`, `id`, `it`, `ja`, `ko`, `pt`, `ru`, `tr`, `vi`, `zh`) y el
menú/ventana respetan la dirección RTL del árabe.

## 2. Opción A: variables de compilación (recomendada)

Copia `.env.example` a `.env` y rellena:

```dotenv
VITE_GOOGLE_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
VITE_DISCORD_CLIENT_ID=123456789012345678
# Opcional: si se omite, se usa <origen actual>/auth/discord-callback.html
# VITE_DISCORD_REDIRECT_URI=http://localhost:5173/auth/discord-callback.html
```

Después reinicia `npm run dev` o vuelve a compilar (`npm run build`).

> Las variables `VITE_*` se incrustan en el build. Si las cambias en el host,
> hay que volver a desplegar para que se apliquen.

En Vercel, Netlify, Cloudflare Pages o Render se añaden en **Environment
Variables** con los mismos nombres. Para producción:

```dotenv
VITE_GOOGLE_CLIENT_ID=...
VITE_DISCORD_CLIENT_ID=...
VITE_DISCORD_REDIRECT_URI=https://tudominio.com/auth/discord-callback.html
```

## 3. Opción B: configuración en runtime (sin recompilar)

Si prefieres inyectar las claves desde el host, coloca esto **antes** del script
de la app (en `index.html` o en la plantilla del host):

```html
<script>
  window.KINORA_AUTH = {
    googleClientId: '1234567890-abc.apps.googleusercontent.com',
    discordClientId: '123456789012345678',
    discordRedirectUri: 'https://tudominio.com/auth/discord-callback.html'
  };
</script>
```

`window.KINORA_AUTH` tiene prioridad sobre las variables `VITE_*`.
Así puedes cambiar las credenciales sin reconstruir el bundle.

Si no se define `discordRedirectUri`, se usa automáticamente:

```text
<origen actual>/auth/discord-callback.html
```

## 4. Configurar Google

1. Entra en [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto (o selecciona uno existente).
3. Ve a **APIs y servicios → Pantalla de consentimiento OAuth**.
   - Tipo: **Externo**.
   - Nombre de la app: `Kinora`.
   - Correo de asistencia.
   - Scopes: `openid`, `email`, `profile`.
   - Si la app está en modo **Prueba**, añade tu cuenta en **Usuarios de prueba**.
4. Ve a **APIs y servicios → Credenciales → Crear credenciales → ID de cliente
   OAuth**.
   - Tipo: **Aplicación web**.
   - **Orígenes JavaScript autorizados**:
     - `http://localhost:5173`
     - `https://tudominio.com`
   - No hace falta añadir una redirect URI para este flujo.
5. Copia el **Client ID** a `VITE_GOOGLE_CLIENT_ID` o a
   `window.KINORA_AUTH.googleClientId`.
6. Espera unos minutos a que Google propague el cambio.

El código pide los scopes `openid email profile` y lee
`https://www.googleapis.com/oauth2/v3/userinfo`. De ahí salen `name`, `email` y
`picture`.

### Errores habituales de Google

- **`origin_mismatch` / `redirect_uri_mismatch`**: el origen no coincide. Debe
  ser exactamente `https://tudominio.com`, sin ruta ni barra final.
- **`Access blocked: app not verified`**: publica la app o añade el usuario de
  prueba en la pantalla de consentimiento.
- **La ventana no se abre**: permite ventanas emergentes para el dominio.

## 5. Configurar Discord

1. Entra en [Discord Developer Portal](https://discord.com/developers/applications).
2. Crea una aplicación con **New Application**.
3. En **OAuth2 → Redirects**, añade exactamente:
   - `http://localhost:5173/auth/discord-callback.html`
   - `https://tudominio.com/auth/discord-callback.html`
4. Copia el **Client ID** de **OAuth2 → General** a `VITE_DISCORD_CLIENT_ID` o a
   `window.KINORA_AUTH.discordClientId`.
5. No uses el **Client Secret** en el frontend. Este código no lo necesita.
6. El scope solicitado es solo `identify`, suficiente para nombre y avatar.
   Si más adelante quieres mostrar también el correo de Discord, cambia en
   `src/lib/auth.jsx` el scope a `identify email` y rellena `email` desde
   `/users/@me`.

La respuesta de Discord vuelve a
`/auth/discord-callback.html#access_token=...`. Esa página envía el token a la
ventana de Kinora por `postMessage` (solo al mismo origen), limpia el hash y se
cierra.

> Discord recomienda el flujo de código con PKCE para producción. La versión
> incluida usa el flujo implícito porque no requiere backend ni client secret.
> Si vas a proteger APIs o suscripciones, cambia a un intercambio de código en
> el servidor (ver sección 8).

### Errores habituales de Discord

- **`Invalid OAuth2 redirect_uri`**: la URL registrada no coincide al 100 %.
  Revisa `http`/`https`, el puerto, la ruta y la barra final.
- **La ventana se cierra y no hay sesión**: comprueba que
  `/auth/discord-callback.html` carga con el dominio real (no debe dar 404).
- **`popup_blocked`**: el navegador bloqueó la ventana. Permite pop-ups.
- **`state_mismatch`**: la respuesta se recibió en otra pestaña o se perdió el
  `sessionStorage`. Vuelve a intentarlo desde el mismo navegador.

## 6. Probar en local

```bash
npm install
npm run dev
```

Abre `http://localhost:5173`:

1. Arriba a la derecha debería aparecer **Iniciar sesión** (en la portada y en
   las fichas).
2. Pulsa el botón y elige Google o Discord.
3. Tras autorizar, el botón se convierte en el avatar.
4. Pulsa el avatar: se abre el menú con nombre, correo (solo Google), proveedor,
   **Ver mi lista** y **Cerrar sesión**.
5. Cierra sesión y comprueba que desaparece la sesión guardada.

Para verificar la clave guardada en el navegador:

```js
localStorage.getItem('kinora:auth-session');
```

## 7. Despliegue

1. Define las variables en el host (o el script `window.KINORA_AUTH`).
2. Ejecuta `npm run build`.
3. Publica `dist/` (o deja que `server.py` lo sirva).
4. Comprueba que `dist/auth/discord-callback.html` existe.
5. Prueba los dos proveedores desde el dominio real, no solo en local.

Si usas un subdominio o una subruta (por ejemplo
`https://tudominio.com/kinora/`), configura `VITE_DISCORD_REDIRECT_URI` de forma
explícita con la URL completa.

## 8. Seguridad y siguientes pasos

La sesión actual es **de cliente**: sirve para mostrar el perfil y personalizar
la interfaz, pero no demuestra identidad ante un servidor. Para producción:

1. Valida en el backend el `access_token` de Google o Discord.
2. Emite una sesión propia con cookie `HttpOnly`, `Secure` y `SameSite=Lax`.
3. No guardes el client secret en el frontend.
4. Usa PKCE y el intercambio de código en el servidor para Discord.
5. Restringe orígenes y redirect URIs en ambos portales.
6. Si añades una CSP, permite estos destinos:
   - `script-src`: `https://accounts.google.com`
   - `connect-src`: `https://www.googleapis.com`, `https://discord.com`
   - `img-src`: `https://cdn.discordapp.com`, `https://lh3.googleusercontent.com`
   - `frame-src` no es necesario para las ventanas emergentes.

## 9. Resumen de variables

| Variable | Obligatoria | Dónde se obtiene |
| --- | --- | --- |
| `VITE_GOOGLE_CLIENT_ID` | Para Google | Google Cloud Console |
| `VITE_DISCORD_CLIENT_ID` | Para Discord | Discord Developer Portal |
| `VITE_DISCORD_REDIRECT_URI` | Recomendada | Debe coincidir con Discord |

También se pueden pasar como `window.KINORA_AUTH.googleClientId`,
`window.KINORA_AUTH.discordClientId` y
`window.KINORA_AUTH.discordRedirectUri`.
