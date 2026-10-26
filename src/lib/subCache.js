/** Caché de subtítulos en localStorage (por dispositivo). */
const PREFIX = 'kinora:sub:v1:';
const MAX_ENTRIES = 80;
const MAX_CHARS = 450_000; // ~ recorte por entrada muy grande

function storageKey(fileId) {
  return `${PREFIX}${fileId}`;
}

export function getCachedSub(fileId) {
  try {
    const raw = localStorage.getItem(storageKey(fileId));
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data?.vtt) return null;
    return data;
  } catch {
    return null;
  }
}

export function setCachedSub(fileId, { vtt, label, language }) {
  try {
    let text = vtt || '';
    if (text.length > MAX_CHARS) text = text.slice(0, MAX_CHARS);
    localStorage.setItem(
      storageKey(fileId),
      JSON.stringify({
        vtt: text,
        label: label || '',
        language: language || '',
        ts: Date.now(),
      })
    );
    prune();
  } catch {
    // quota llena: limpiar viejos e intentar una vez
    try {
      prune(true);
      localStorage.setItem(
        storageKey(fileId),
        JSON.stringify({ vtt, label, language, ts: Date.now() })
      );
    } catch {
      /* ignore */
    }
  }
}

function prune(aggressive = false) {
  const keys = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith(PREFIX)) keys.push(k);
  }
  const limit = aggressive ? Math.floor(MAX_ENTRIES / 2) : MAX_ENTRIES;
  if (keys.length <= limit) return;
  const scored = keys
    .map(k => {
      try {
        const d = JSON.parse(localStorage.getItem(k) || '{}');
        return { k, ts: d.ts || 0 };
      } catch {
        return { k, ts: 0 };
      }
    })
    .sort((a, b) => a.ts - b.ts);
  const drop = scored.length - limit;
  for (let i = 0; i < drop; i++) localStorage.removeItem(scored[i].k);
}