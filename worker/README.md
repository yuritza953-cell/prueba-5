# CineBusca HLS Worker

Proxy firmado para segmentos HLS/MP4. El backend resuelve el stream y firma la URL;
este Worker verifica la firma y trae el media **sin pasar por Render**.

## Requisitos

1. Misma clave `STREAM_SIGN_KEY` en:
   - Backend (Render): variable de entorno
   - Worker: `wrangler secret put STREAM_SIGN_KEY`
2. Backend: `STREAM_WORKER_BASE=https://tu-worker.workers.dev` (o tu dominio)

## Deploy

```bash
cd worker
npx wrangler login
npx wrangler secret put STREAM_SIGN_KEY
npx wrangler deploy
```

Cuando tengas dominio propio, descomenta `[[routes]]` en `wrangler.toml`.

## Ampliar hosts

Edita `HOST_SUFFIXES` en `src/worker.js` y vuelve a desplegar.
