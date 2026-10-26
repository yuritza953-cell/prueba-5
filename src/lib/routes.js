// Rutas legibles para las pantallas de Kinora: /peliculas, /series, /series/dune…
// El nombre de la categoria se toma del idioma activo, con alias de todos los
// diccionarios para que un enlace viejo (o en otro idioma) siga resolviendo.
import { LOCALES } from '../i18n';

const FALLBACK = { movie: 'movies', tv: 'series', list: 'my-list' };

/** Texto → segmento de URL. Conserva alfabetos no latinos (ru, ja, ar…). */
export function slugify(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/['"’]/g, '')
    .replace(/[^\p{L}\p{N}\p{M}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 90);
}

export const mediaOf = item => (item?.media === 'tv' ? 'tv' : 'movie');

export function categorySlug(media, t) {
  const kind = media === 'tv' ? 'tv' : 'movie';
  const word = kind === 'tv' ? t('home.series') : t('home.movies');
  return slugify(word) || FALLBACK[kind];
}

const CATEGORIES = new Map();
const LISTS = new Set();

const addCategory = (word, media) => {
  const slug = slugify(word);
  if (slug && !CATEGORIES.has(slug)) CATEGORIES.set(slug, media);
};

Object.keys(FALLBACK)
  .filter(key => key !== 'list')
  .forEach(key => CATEGORIES.set(FALLBACK[key], key));

Object.values(LOCALES).forEach(dict => {
  addCategory(dict?.home?.movies, 'movie');
  addCategory(dict?.home?.series, 'tv');
  const list = slugify(dict?.nav?.list);
  if (list) LISTS.add(list);
});

// Alias cortos que la gente escribe a mano.
[
  ['movie', 'movie'],
  ['movies', 'movie'],
  ['film', 'movie'],
  ['films', 'movie'],
  ['pelicula', 'movie'],
  ['peliculas', 'movie'],
  ['tv', 'tv'],
  ['serie', 'tv'],
  ['series', 'tv'],
  ['shows', 'tv']
].forEach(([word, media]) => addCategory(word, media));

['list', 'lista', 'mi-lista', 'my-list', 'minha-lista', 'meine-liste'].forEach(word => LISTS.add(slugify(word)));

/** Ruta (pathname + query) que corresponde a un estado de pantalla. */
export function pathFor(route, t) {
  if (!route || route.name === 'home') return '/';

  if (route.name === 'collection') return `/${categorySlug(route.media, t)}`;

  if (route.name === 'title' || route.name === 'watch') {
    const item = route.item;
    if (!item) return '/';
    const media = mediaOf(item);
    const slug = slugify(item.title || item.name) || `titulo-${item.id ?? ''}`;
    const base = `/${categorySlug(media, t)}/${slug}`;
    return route.name === 'watch' ? `${base}/watch` : base;
  }

  if (route.name === 'list') return `/${slugify(t('nav.list')) || FALLBACK.list}`;

  if (route.name === 'search') return `/buscar?q=${encodeURIComponent(route.query || '')}`;

  return '/';
}

/** Estado de pantalla a partir de la URL. Nunca rompe el flujo: la app decide. */
export function parsePath(pathname, search, t) {
  const path = String(pathname || '/').replace(/\/+$/, '');
  const params = new URLSearchParams(search || '');

  if (!path) return { name: 'home' };

  if (path === '/buscar') {
    const query = (params.get('q') || '').trim();
    if (!query) return { name: 'home' };
    return {
      name: 'search',
      query,
      filters: { type: params.get('tipo') || 'all', audio: params.get('audio') || 'all' },
      items: [],
      page: 0,
      totalPages: 1,
      loading: true,
      more: false,
      error: ''
    };
  }

  let parts;
  try {
    parts = path
      .slice(1)
      .split('/')
      .map(part => decodeURIComponent(part))
      .filter(Boolean);
  } catch {
    return { name: 'home', unknown: true };
  }

  if (!parts.length) return { name: 'home' };

  const first = slugify(parts[0]);

  if (LISTS.has(first)) {
    return {
      name: 'list',
      title: t('nav.list'),
      subtitle: t('browse.emptyText'),
      items: [],
      page: 1,
      totalPages: 1,
      loading: false,
      more: false,
      error: ''
    };
  }

  const media = CATEGORIES.get(first);
  if (media === 'movie' || media === 'tv') {
    if (parts.length === 1) {
      return {
        name: 'collection',
        media,
        category: 'popular',
        title: t(media === 'tv' ? 'home.series' : 'home.movies'),
        subtitle: t('browse.popular'),
        items: [],
        page: 0,
        totalPages: 1,
        loading: true,
        more: false,
        error: ''
      };
    }
    const slug = slugify(parts[1]);
    if (slug) return { name: 'title', item: null, media, slug };
  }

  return { name: 'home', unknown: true };
}
