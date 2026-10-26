export const KIND_LABEL = { movie: 'Película', tv: 'Serie', anime: 'Anime' };
export const AUDIO_LABEL = { sub: 'Subtitulado', dub: 'Doblaje' };
export const AUDIO_SHORT = { sub: 'Sub', dub: 'Dob' };

const ACCENTS = ['#5ea0ff', '#7cc4ff', '#a98bff', '#ff7eb6', '#ffd23f', '#3fb8ff'];

export const mediaKey = item => `${item?.media ?? 'movie'}-${item?.id ?? item?.title ?? ''}`;

export const kindLabel = item => KIND_LABEL[item?.kind] ?? 'Película';

export const audioBadge = audios =>
  audios?.length ? audios.map(audio => AUDIO_SHORT[audio] ?? audio).join(' · ') : '';

// Filtro de audio original del titulo; decide el idioma con el que se pide la ficha.
export const audioFilter = item =>
  item?.audio_filter ?? (item?.audio?.length ? item.audio.join(',') : 'sub');

export const formatVotes = votes => (votes ? Number(votes).toLocaleString('es-ES') : '');

// Adapta un titulo normalizado de TMDB al formato que espera ChromaGrid.
export const toChromaItem = (item, index, kindText) => ({
  ...item,
  image: item.poster ?? item.backdrop,
  subtitle: [kindText ?? kindLabel(item), item.year, item.rating ? `★ ${item.rating}` : null].filter(Boolean).join(' · '),
  accent: ACCENTS[index % ACCENTS.length],
  badge: audioBadge(item.audio)
});

export async function api(path, params = {}, signal) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const url = query.toString() ? `${path}?${query}` : path;
  const res = await fetch(url, { signal });
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) throw new Error(data?.error || `El servidor respondió ${res.status}`);
  return data;
}
