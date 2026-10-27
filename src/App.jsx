import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import TopBar from './components/TopBar';
import SearchStage from './components/SearchStage';
import BrowseView from './components/BrowseView';
import TitleView from './components/TitleView';
import WatchView from './components/WatchView';
import OverlayScrollbar from './components/OverlayScrollbar';
import CookieBanner from './components/CookieBanner';
import Footer from './components/Footer';
import InPagePush from './components/InPagePush';
import { AD_SLOTS } from './lib/ads';
import { useT, useI18n } from './i18n';
import { streamLangFor } from './lib/audioLangs';
import { api, audioFilter, mediaKey } from './lib/media';
import { mediaOf, parsePath, pathFor, slugify } from './lib/routes';
import './App.css';

const SAVED_KEY = 'kinora:mi-lista';
const cacheKey = item => `${mediaKey(item)}|${audioFilter(item)}`;

const readSaved = () => {
  try {
    if (typeof window === 'undefined') return [];
    const raw = window.localStorage.getItem(SAVED_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(item => item && item.id) : [];
  } catch {
    return [];
  }
};

// Fondo de la app: la imagen del titulo abierto entra y sale con un fundido
// cruzado para que el cambio entre la portada y la ficha no sea brusco.
function AppBackdrop({ art }) {
  const [layer, setLayer] = useState(() => ({ url: art, token: 0, leaving: false }));

  useEffect(() => {
    if (art) {
      setLayer(current => (current.url === art ? current : { url: art, token: current.token + 1, leaving: false }));
      return;
    }
    setLayer(current => (current.url ? { ...current, leaving: true } : current));
  }, [art]);

  useEffect(() => {
    if (!layer.leaving) return undefined;
    const timer = window.setTimeout(() => setLayer(current => ({ ...current, url: null })), 760);
    return () => window.clearTimeout(timer);
  }, [layer.leaving, layer.token]);

  return (
    <div className="app__bg" aria-hidden="true">
      <div className="app__gradient" />
      {layer.url ? (
        <div
          key={layer.token}
          className={`app__art${layer.leaving ? ' app__art--out' : ''}`}
          style={{ backgroundImage: `url(${layer.url})` }}
        />
      ) : null}
      <div className="app__vignette" />
    </div>
  );
}

export default function App() {
  const t = useT();
  const { setLocale } = useI18n();
  const [home, setHome] = useState(null);

  const [route, setRoute] = useState(() =>
    typeof window === 'undefined'
      ? { name: 'home' }
      : parsePath(window.location.pathname, window.location.search, t)
  );
  const routeRef = useRef(route);
  const [stack, setStack] = useState([]);
  const stackRef = useRef(stack);
  const tRef = useRef(t);
  const collectionToken = useRef(0);
  const searchUrlRef = useRef('');

  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(readSaved);
  const [dubLang, setDubLang] = useState(() => {
    try {
      return localStorage.getItem('kinora_dub_lang') || 'es-MX';
    } catch {
      return 'es-MX';
    }
  });

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [detailNonce, setDetailNonce] = useState(0);

  const [related, setRelated] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [titleShelves, setTitleShelves] = useState([]);
  const [shelvesLoading, setShelvesLoading] = useState(false);

  const searchAbort = useRef(null);
  const detailToken = useRef(0);
  const relatedToken = useRef(0);
  const detailCache = useRef(new Map());
  const relatedCache = useRef(new Map());
  const shelvesCache = useRef(new Map());
  const shelvesToken = useRef(0);

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  useEffect(() => {
    stackRef.current = stack;
  }, [stack]);

  useEffect(() => {
    tRef.current = t;
  }, [t]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SAVED_KEY, JSON.stringify(saved));
    } catch {
      // Sin almacenamiento disponible: la lista sigue viva en memoria.
    }
  }, [saved]);

  // Catalogo de TMDB: alimenta las sugerencias de la portada y "Sorprendeme".
  useEffect(() => {
    const controller = new AbortController();
    api('/api/home', {}, controller.signal)
      .then(data => setHome(data))
      .catch(() => setHome(null));
    return () => controller.abort();
  }, []);

  // Ficha y relacionados del título abierto (con cache en memoria).
  const activeItem = route.name === 'title' || route.name === 'watch' ? route.item : null;

  useEffect(() => {
    if (!activeItem) return undefined;
    const key = cacheKey(activeItem);
    const token = ++detailToken.current;
    const relToken = ++relatedToken.current;
    const cached = detailCache.current.get(key);
    const cachedRelated = relatedCache.current.get(key);
    const audio = audioFilter(activeItem);

    setDetailError('');
    setRelated(cachedRelated ?? []);
    setRelatedLoading(!cachedRelated);

    if (cached) {
      setDetail(cached);
      setDetailLoading(false);
    } else {
      setDetail(null);
      setDetailLoading(true);
      api('/api/detail', { id: activeItem.id, media: activeItem.media, audio })
        .then(data => {
          if (token !== detailToken.current) return;
          detailCache.current.set(key, data);
          setDetail(data);
        })
        .catch(error => {
          if (token === detailToken.current && error.name !== 'AbortError') setDetailError(error.message);
        })
        .finally(() => {
          if (token === detailToken.current) setDetailLoading(false);
        });
    }

    if (!cachedRelated) {
      api('/api/related', { id: activeItem.id, media: activeItem.media, audio })
        .then(data => {
          if (relToken !== relatedToken.current) return;
          const items = data?.items ?? [];
          relatedCache.current.set(key, items);
          setRelated(items);
        })
        .catch(() => {
          if (relToken === relatedToken.current) setRelated([]);
        })
        .finally(() => {
          if (relToken === relatedToken.current) setRelatedLoading(false);
        });
    }

    return undefined;
  }, [activeItem, detailNonce]);

  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  // La URL acompaña a la pantalla sin recargar: pushState mantiene vivo el flujo
  // (ficha, reproductor, vuelta atrás) y un refresco cae en la misma vista.

  useEffect(() => {
    if (!activeItem) return undefined;
    const key = cacheKey(activeItem);
    const token = ++shelvesToken.current;
    const cached = shelvesCache.current.get(key);
    if (cached) {
      setTitleShelves(cached);
      setShelvesLoading(false);
      return undefined;
    }
    setShelvesLoading(true);
    api('/api/title_shelves', { id: activeItem.id, media: activeItem.media || 'movie', audio: audioFilter(activeItem) })
      .then(data => {
        if (token !== shelvesToken.current) return;
        const shelves = data?.shelves || [];
        shelvesCache.current.set(key, shelves);
        setTitleShelves(shelves);
      })
      .catch(() => {
        if (token === shelvesToken.current) setTitleShelves([]);
      })
      .finally(() => {
        if (token === shelvesToken.current) setShelvesLoading(false);
      });
    return undefined;
  }, [activeItem, dubLang]);

  const writeUrl = useCallback((next, options = {}) => {
    if (typeof window === 'undefined') return;
    if (next?.name === 'title' && !next.item) return;
    const path = pathFor(next, tRef.current);
    const current = `${window.location.pathname}${window.location.search}`;
    if (path === current) return;
    try {
      if (options.replace) window.history.replaceState({ path }, '', path);
      else window.history.pushState({ path }, '', path);
    } catch {
      /* historial bloqueado: la app sigue funcionando */
    }
  }, []);

  const applyRoute = useCallback(
    (next, options = {}) => {
      routeRef.current = next;
      setRoute(next);
      writeUrl(next, options);
      if (options.scroll !== false) scrollTop();
    },
    [writeUrl]
  );

  const go = useCallback(
    next => {
      const current = routeRef.current;
      if (!(current.name === 'search' && next.name === 'search')) {
        setStack(list => [...list, current]);
      }
      applyRoute(next);
    },
    [applyRoute]
  );

  const openHome = useCallback(
    (options = {}) => {
      setStack([]);
      applyRoute({ name: 'home' }, options);
    },
    [applyRoute]
  );

  const back = () => {
    if (!stackRef.current.length) {
      setStack([]);
      applyRoute({ name: 'home' }, { replace: true });
      return;
    }
    // El historial ya tiene la pantalla anterior: popstate restaura su estado.
    window.history.back();
  };

  const openTitle = item => go({ name: 'title', item });

  const openWatch = (item, options = {}) =>
    go({
      name: 'watch',
      item,
      season: options.season ?? null,
      episode: options.episode ?? null
    });

  const stopSearch = () => {
    searchAbort.current?.abort();
    searchAbort.current = null;
    setBusy(false);
    setRoute(current => (current.name === 'search' ? { ...current, loading: false } : current));
  };

  const runSearch = useCallback(
    async (text, options = {}, meta = {}) => {
      const query = (text ?? '').trim();
      if (!query) return;

      searchAbort.current?.abort();
      const controller = new AbortController();
      searchAbort.current = controller;

      if (options.lang?.key) setDubLang(options.lang.key);
      const filters = { type: options.model?.key ?? 'all', audio: options.audio?.key ?? 'all' };
      const next = {
        name: 'search',
        query,
        filters,
        items: [],
        page: 0,
        totalPages: 1,
        loading: true,
        more: false,
        error: ''
      };

      const current = routeRef.current;
      if (!meta.fromUrl && !(current.name === 'search' && current.query === query)) {
        setStack(list => [...list, current]);
      }
      searchUrlRef.current = `${query}|${filters.type}|${filters.audio}`;
      applyRoute(next, { replace: Boolean(meta.fromUrl) });
      setBusy(true);

      try {
        const data = await api(
          '/api/search',
          { q: query, type: filters.type, audio: filters.audio, page: 1 },
          controller.signal
        );
        if (controller.signal.aborted) return;
        setRoute(currentRoute =>
          currentRoute.name === 'search' && currentRoute.query === query
            ? {
                ...currentRoute,
                items: data.results ?? [],
                page: data.page ?? 1,
                totalPages: data.total_pages ?? 1,
                loading: false
              }
            : currentRoute
        );
      } catch (error) {
        if (controller.signal.aborted) return;
        setRoute(currentRoute =>
          currentRoute.name === 'search' && currentRoute.query === query
            ? { ...currentRoute, loading: false, error: error.message }
            : currentRoute
        );
      } finally {
        if (searchAbort.current === controller) setBusy(false);
      }
    },
    [applyRoute]
  );

  const loadMoreSearch = async () => {
    const active = routeRef.current;
    if (active.name !== 'search' || active.loading || active.more || active.page >= active.totalPages) return;
    setRoute({ ...active, more: true });
    try {
      const data = await api('/api/search', {
        q: active.query,
        type: active.filters.type,
        audio: active.filters.audio,
        page: active.page + 1
      });
      setRoute(current =>
        current.name === 'search' && current.query === active.query
          ? {
              ...current,
              items: [...current.items, ...(data.results ?? [])],
              page: data.page ?? active.page + 1,
              totalPages: data.total_pages ?? active.totalPages,
              more: false
            }
          : current
      );
    } catch (error) {
      setRoute(current => (current.name === 'search' ? { ...current, more: false, error: error.message } : current));
    }
  };

  const collectionState = media => ({
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
  });

  // La carga vive en un efecto para que una URL abierta directamente
  // (/peliculas, /series) tambien se rellene igual que si se hubiera pulsado.
  const openBrowse = media => go(collectionState(media));

  useEffect(() => {
    if (route.name !== 'collection' || !route.media || !route.loading) return undefined;
    const token = ++collectionToken.current;
    const media = route.media;
    api('/api/browse', { media, category: route.category ?? 'popular', page: 1 })
      .then(data => {
        if (token !== collectionToken.current) return;
        setRoute(current =>
          current.name === 'collection' && current.media === media
            ? {
                ...current,
                items: data.items ?? [],
                page: data.page ?? 1,
                totalPages: data.total_pages ?? 1,
                loading: false
              }
            : current
        );
      })
      .catch(error => {
        if (token !== collectionToken.current) return;
        setRoute(current =>
          current.name === 'collection' && current.media === media
            ? { ...current, loading: false, error: error.message }
            : current
        );
      });
    return undefined;
  }, [route.name, route.media, route.loading, route.category]);

  const loadMoreCollection = async () => {
    const active = routeRef.current;
    if (active.name !== 'collection' || !active.media || active.more || active.loading || active.page >= active.totalPages) {
      return;
    }
    setRoute({ ...active, more: true });
    try {
      const data = await api('/api/browse', {
        media: active.media,
        category: active.category ?? 'popular',
        page: active.page + 1
      });
      setRoute(current =>
        current.name === 'collection' && current.title === active.title
          ? {
              ...current,
              items: [...current.items, ...(data.items ?? [])],
              page: data.page ?? active.page + 1,
              totalPages: data.total_pages ?? active.totalPages,
              more: false
            }
          : current
      );
    } catch (error) {
      setRoute(current => (current.name === 'collection' ? { ...current, more: false, error: error.message } : current));
    }
  };

  const openList = () => {
    go({
      name: 'list',
      title: t('nav.list'),
      subtitle: t('browse.emptyText'),
      items: [],
      page: 1,
      totalPages: 1,
      loading: false,
      more: false,
      error: ''
    });
  };

  // Atrás/adelante del navegador: se restaura la pantalla anterior tal cual.
  useEffect(() => {
    const onPop = () => {
      const pending = stackRef.current;
      if (pending.length) {
        const previous = pending[pending.length - 1];
        setStack(pending.slice(0, -1));
        routeRef.current = previous;
        setRoute(previous);
        scrollTop();
        return;
      }
      const parsed = parsePath(window.location.pathname, window.location.search, tRef.current);
      routeRef.current = parsed;
      setRoute(parsed);
      scrollTop();
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // URL desconocida: se limpia sin dejar una entrada muerta en el historial.
  useEffect(() => {
    if (!routeRef.current?.unknown) return;
    applyRoute({ name: 'home' }, { replace: true, scroll: false });
  }, [applyRoute]);

  // Al cambiar de idioma, la categoría del enlace se adapta (peliculas → movies).
  useEffect(() => {
    const active = routeRef.current;
    if (active.name === 'collection' && active.media) {
      setRoute(current =>
        current.name === 'collection'
          ? {
              ...current,
              title: t(current.media === 'tv' ? 'home.series' : 'home.movies'),
              subtitle: t('browse.popular')
            }
          : current
      );
    }
    if (typeof window === 'undefined') return;
    if (active.name === 'title' && !active.item) return;
    const path = pathFor(active, t);
    const currentPath = `${window.location.pathname}${window.location.search}`;
    if (path !== currentPath) {
      try {
        window.history.replaceState({ path }, '', path);
      } catch {
        /* historial bloqueado */
      }
    }
  }, [t]);

  // URL de ficha (/series/one-punch-man): se resuelve el título y se abre igual
  // que desde una tarjeta, sin recargar la página.
  useEffect(() => {
    if (route.name !== 'title' || route.item) return undefined;
    const slug = route.slug;
    const media = route.media === 'tv' ? 'tv' : 'movie';
    const words = slug.replace(/[-_.]+/g, ' ').trim();
    if (!words) {
      applyRoute({ name: 'home' }, { replace: true });
      return undefined;
    }
    let cancelled = false;
    api('/api/search', { q: words, type: media, audio: 'all', page: 1 })
      .then(data => {
        if (cancelled) return;
        const results = data?.results ?? [];
        const match =
          results.find(entry => slugify(entry.title) === slug && mediaOf(entry) === media) ||
          results.find(entry => slugify(entry.title) === slug) ||
          results[0];
        if (!match) {
          runSearch(words, { model: { key: media }, audio: { key: 'all' } }, { fromUrl: true });
          return;
        }
        const next = { name: 'title', item: match };
        routeRef.current = next;
        setRoute(next);
        writeUrl(next, { replace: true });
      })
      .catch(() => {
        if (!cancelled) {
          runSearch(words, { model: { key: media }, audio: { key: 'all' } }, { fromUrl: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [route.name, route.item, route.slug, route.media, applyRoute, runSearch, writeUrl]);

  // /buscar?q=… también sobrevive a un refresco.
  useEffect(() => {
    if (route.name !== 'search' || !route.loading || !route.query) return;
    const filters = route.filters ?? { type: 'all', audio: 'all' };
    const key = `${route.query}|${filters.type}|${filters.audio}`;
    if (searchUrlRef.current === key) return;
    runSearch(route.query, { model: { key: filters.type }, audio: { key: filters.audio } }, { fromUrl: true });
  }, [route, runSearch]);

  const isSaved = useCallback(
    item => Boolean(item) && saved.some(entry => mediaKey(entry) === mediaKey(item)),
    [saved]
  );

  const toggleSaved = useCallback(item => {
    if (!item?.id) return;
    setSaved(list => {
      const key = mediaKey(item);
      if (list.some(entry => mediaKey(entry) === key)) {
        return list.filter(entry => mediaKey(entry) !== key);
      }
      return [item, ...list];
    });
  }, []);

  const retryDetail = () => {
    if (!activeItem) return;
    detailCache.current.delete(cacheKey(activeItem));
    relatedCache.current.delete(cacheKey(activeItem));
    setDetailNonce(value => value + 1);
  };

  const catalogue = useMemo(
    () => (home ? [...(home.hero ?? []), ...(home.rows ?? []).flatMap(row => row.items ?? [])] : []),
    [home]
  );

  const homeSuggestions = useMemo(() => {
    const seen = new Set();
    return catalogue
      .filter(item => {
        if (!item?.id || !item?.title) return false;
        const key = mediaKey(item);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 6);
  }, [catalogue]);

  const shufflePool = catalogue;

  const shuffle = () => {
    if (!shufflePool.length) return;
    openTitle(shufflePool[Math.floor(Math.random() * shufflePool.length)]);
  };

  const artItem = route.name === 'title' || route.name === 'watch' ? route.item : null;
  const artMedia = artItem ? artItem.media ?? (artItem.kind === 'anime' ? 'tv' : artItem.kind) : null;
  const detailMatches = Boolean(detail && artItem && detail.id === artItem.id && detail.kind === artMedia);
  const art = artItem?.backdrop || (detailMatches ? detail?.backdrop : null) || artItem?.poster || null;

  return (
    <div className="app" data-view={route.name}>
      <AppBackdrop art={art} />

      {/* En /watch el banner móvil va dentro de la columna lateral, no encima
          de la barra inferior: así no se juntan dos bloques sobre el vídeo. */}
      {route.name !== 'home' ? (
        <TopBar
          onHome={openHome}
          onBack={back}
          onSearch={runSearch}
          onStop={stopSearch}
          busy={busy}
          onList={openList}
          savedCount={saved.length}
          dubLang={dubLang}
          showMobileAd={route.name !== 'watch'}
          onDubLangChange={code => {
            setDubLang(code);
            try { localStorage.setItem('kinora_dub_lang', code); } catch {}
            setLocale(code);
          }}
        />
      ) : null}

      {route.name === 'home' ? (
        <SearchStage
          key="stage"
          suggestions={homeSuggestions}
          busy={busy}
          savedCount={saved.length}
          canShuffle={shufflePool.length > 0}
          onSubmit={runSearch}
          onStop={stopSearch}
          onOpen={openTitle}
          onList={openList}
          onBrowse={openBrowse}
          onShuffle={shuffle}
          dubLang={dubLang}
          onDubLangChange={code => {
            setDubLang(code);
            try { localStorage.setItem('kinora_dub_lang', code); } catch {}
            setLocale(code);
          }}
        />
      ) : null}

      {route.name === 'search' ? (
        <BrowseView
          key={`search-${route.query}-${route.filters.type}-${route.filters.audio}`}
          eyebrow={t('search.eyebrow')}
          title={t('search.resultsFor', { q: route.query })}
          description={t('search.description', {
            type: t(`types.${route.filters.type || 'all'}`),
            audio: t(`audio.${route.filters.audio || 'all'}`)
          })}
          count={route.items.length}
          items={route.items}
          loading={route.loading}
          error={route.error}
          onOpen={openTitle}
          onLoadMore={loadMoreSearch}
          hasMore={!route.loading && route.page < route.totalPages}
          loadingMore={route.more}
          emptyTitle={t('search.emptyTitle')}
          emptyText={t('search.emptyText', { q: route.query })}
          suggestions={['Dune', 'Breaking Bad', 'Your Name']}
          onSuggestion={text => runSearch(text, { model: { key: route.filters.type }, audio: { key: route.filters.audio } })}
        />
      ) : null}

      {route.name === 'collection' ? (
        <BrowseView
          key={`collection-${route.title}-${route.media ?? 'mix'}`}
          eyebrow={t('browse.eyebrow')}
          title={route.title}
          description={route.subtitle}
          count={route.items.length}
          items={route.items}
          loading={route.loading}
          error={route.error}
          onOpen={openTitle}
          onLoadMore={loadMoreCollection}
          hasMore={Boolean(route.media) && route.page < route.totalPages}
          loadingMore={route.more}
          emptyTitle={t('browse.emptyTitle')}
          emptyText={t('browse.emptyText')}
        />
      ) : null}

      {route.name === 'list' ? (
        <BrowseView
          key="mi-lista"
          eyebrow={t('nav.list')}
          title={t('nav.list')}
          description=""
          count={saved.length}
          items={saved}
          onOpen={openTitle}
          emptyTitle={t('browse.emptyTitle')}
          emptyText={t('browse.emptyText')}
          action={
            <button type="button" className="btn btn--info browse__head-action" onClick={openHome}>
              {t('footer.explore')}
            </button>
          }
        />
      ) : null}

      {route.name === 'title' && !route.item ? (
        <main className="route-loading view" aria-busy="true" aria-label={t('common.loading')}>
          <div className="shell">
            <span className="route-loading__ring" />
          </div>
        </main>
      ) : null}

      {route.name === 'title' && route.item ? (
        <TitleView
          key={`title-${mediaKey(route.item)}`}
          item={route.item}
          detail={detailMatches ? detail : null}
          loading={detailLoading}
          error={detailError}
          related={related}
          relatedLoading={relatedLoading}
          shelves={titleShelves}
          shelvesLoading={shelvesLoading}
          saved={isSaved(route.item)}
          onToggleSaved={toggleSaved}
          onPlay={openWatch}
          onOpen={openTitle}
          onRetry={retryDetail}
        />
      ) : null}

      {route.name === 'watch' ? (
        <WatchView
          key={`watch-${mediaKey(route.item)}`}
          item={route.item}
          detail={detailMatches ? detail : null}
          loading={detailLoading}
          error={detailError}
          related={related}
          relatedLoading={relatedLoading}
          initialSeason={route.season}
          initialEpisode={route.episode}
          saved={isSaved(route.item)}
          onToggleSaved={toggleSaved}
          onOpenTitle={openTitle}
          preferredLang={streamLangFor(dubLang)}
        />
      ) : null}

      {/* Formato in-page push: nunca sobre el reproductor ni en la portada. */}
      <InPagePush src={AD_SLOTS.inPagePush} enabled={route.name !== 'watch' && route.name !== 'home'} />

      <CookieBanner />
      <Footer onHome={openHome} onList={openList} onBrowse={openBrowse} onShuffle={shuffle} />
      <OverlayScrollbar />
    </div>
  );
}