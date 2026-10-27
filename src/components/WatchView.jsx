import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, ChevronLeft, ChevronRight, Download, Info, Loader2, Plus, Star } from 'lucide-react';
import AnimatedList from './AnimatedList';
import AdSlot from './AdSlot';
import PeekRating from './PeekRating';
import StreamPlayer from './StreamPlayer';
import RubberSegment from './RubberSegment';
import { api, audioFilter } from '../lib/media';
import { AD_SLOTS } from '../lib/ads';
import { normalizeAudioLang, labelForLang, AUDIO_LANGS } from '../lib/audioLangs';
import { useT } from '../i18n';
import './WatchView.css';

/** Idioma de audio por defecto según ficha + preferencia del usuario. */
function defaultAudioLang(item, preferred = 'es-MX') {
  const audio = audioFilter(item);
  if (audio === 'sub') return 'en';
  return normalizeAudioLang(preferred);
}

export default function WatchView({
  item,
  detail,
  loading = false,
  error = '',
  related = [],
  relatedLoading = false,
  initialSeason = null,
  initialEpisode = null,
  saved = false,
  onToggleSaved,
  onOpenTitle,
  preferredLang = 'es-MX'
}) {
  const t = useT();
  const isSeries = (item?.media ?? detail?.kind) === 'tv';
  const seasons = detail?.seasons ?? [];

  const [season, setSeason] = useState(initialSeason ?? null);
  const [episodes, setEpisodes] = useState([]);
  const [episode, setEpisode] = useState(null);
  const [streamData, setStreamData] = useState(null);
  const [streamLoading, setStreamLoading] = useState(false);
  const [streamError, setStreamError] = useState('');
  const [audioLang, setAudioLang] = useState(() => defaultAudioLang(item, preferredLang));
  const [expanded, setExpanded] = useState(false);
  const [listVersion, setListVersion] = useState(0);
  const [seasonMenu, setSeasonMenu] = useState(false);

  const pendingEpisode = useRef(initialEpisode ?? null);
  const listClick = useRef(false);
  const pickerRef = useRef(null);
  const playerRef = useRef(null);
  const seasonToken = useRef(0);
  const streamToken = useRef(0);

  // Con la ficha cargada: temporada pedida o la primera.
  useEffect(() => {
    if (!isSeries || !seasons.length) return;
    setSeason(current => {
      if (current !== null && seasons.some(entry => entry.number === current)) return current;
      const wanted = initialSeason && seasons.some(entry => entry.number === initialSeason) ? initialSeason : seasons[0].number;
      return wanted;
    });
  }, [isSeries, seasons, initialSeason]);

  // Si el episodio cambia desde "anterior/siguiente", la lista se remonta para
  // que el resaltado coincida con el episodio que se esta reproduciendo.
  useEffect(() => {
    if (!episode) return;
    if (listClick.current) {
      listClick.current = false;
      return;
    }
    setListVersion(value => value + 1);
  }, [episode]);

  // Episodios de la temporada activa.
  useEffect(() => {
    if (!isSeries || season === null || !detail?.id) return undefined;
    const token = ++seasonToken.current;
    setEpisodes([]);
    setEpisode(null);
    const params = {
      id: detail.id,
      season,
      audio: audioFilter(item)
    };
    api('/api/season', params)
      .then(data => {
        if (token !== seasonToken.current) return;
        const list = data?.episodes ?? [];
        const wanted = pendingEpisode.current;
        pendingEpisode.current = null;
        setEpisodes(list);
        setEpisode(list.find(entry => entry.number === wanted) ?? list[0] ?? null);
      })
      .catch(() => {
        if (token === seasonToken.current) setEpisodes([]);
      });
    return undefined;
  }, [isSeries, season, detail?.id, item]);

  useEffect(() => {
    setAudioLang(defaultAudioLang(item, preferredLang));
  }, [item?.id, preferredLang]);

  // Resolución de stream real (HLS/MP4) vía backend híbrido.
  useEffect(() => {
    const id = detail?.id ?? item?.id;
    if (!id) return undefined;

    // Series: esperar a tener episodio elegido.
    if (isSeries && (!episode || season === null)) {
      setStreamData(null);
      setStreamError('');
      return undefined;
    }

    const token = ++streamToken.current;
    setStreamLoading(true);
    setStreamError('');
    setStreamData(null);

    const params = {
      id,
      media: isSeries ? 'tv' : 'movie',
      lang: audioLang,
      imdb: detail?.imdb_id || item?.imdb_id || undefined
    };
    if (isSeries) {
      params.season = season;
      params.episode = episode.number;
    }

    api('/api/stream', params)
      .then(data => {
        if (token !== streamToken.current) return;
        setStreamData(data);
        if (!data?.ok) {
          const langLabel = labelForLang(audioLang, t);
          const msg = isSeries
            ? t('player.langUnavailableSeries', { lang: langLabel })
            : t('player.langUnavailable', { lang: langLabel });
          setStreamError(msg);
        } else if (data?.lang_fallback) {
          const got = labelForLang(data.lang || 'en', t);
          const wanted = labelForLang(audioLang, t);
          setStreamError(''); // no bloquea reproducción
          console.info(`[Kinora] Audio: no hay ${wanted}, reproduciendo en ${got}`);
        } else {
          setStreamError('');
        }
      })
      .catch(err => {
        if (token !== streamToken.current) return;
        setStreamError(err?.message || t('player.unavailable'));
        setStreamData(null);
      })
      .finally(() => {
        if (token === streamToken.current) setStreamLoading(false);
      });

    return undefined;
  }, [detail?.id, item, isSeries, season, episode, preferredLang, audioLang, t]);

  // Con muchas temporadas el menu se cierra al tocar fuera.
  useEffect(() => {
    if (!seasonMenu) return undefined;
    const onDown = event => {
      if (!pickerRef.current?.contains(event.target)) setSeasonMenu(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [seasonMenu]);

  useEffect(() => {
    setSeasonMenu(false);
  }, [season]);

  // Escape cierra el menu de temporadas (el reproductor gestiona el suyo).
  useEffect(() => {
    const onKey = event => {
      if (event.key !== 'Escape' || document.fullscreenElement) return;
      if (seasonMenu) setSeasonMenu(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [seasonMenu]);

  const poster = isSeries ? episode?.still || detail?.backdrop || item?.backdrop : detail?.backdrop || item?.backdrop;

  const rating = Number(detail?.rating ?? item?.rating ?? 0);
  const genres = detail?.genres ?? [];
  const audios = detail?.audio ?? item?.audio ?? [];
  const overview = isSeries && episode ? episode.overview || detail?.overview : detail?.overview || item?.overview || '';
  const kindText = item?.kind === 'tv' ? t('home.series') : item?.kind === 'anime' ? 'Anime' : t('home.movies');
  const long = overview.length > 300;
  const about = expanded || !long ? overview : `${overview.slice(0, 300).trimEnd()}…`;

  const year = detail?.year || item?.year;
  const currentSeason = seasons.find(entry => entry.number === season) ?? null;
  const seasonsText = seasons.length
    ? seasons.length === 1
      ? t('title.seasonCountOne')
      : t('title.seasonCount', { n: seasons.length })
    : '';
  const runtimeText = detail?.runtime ? `${detail.runtime} min` : seasonsText;

  const episodeIndex = episodes.findIndex(entry => entry.number === episode?.number);
  const jump = delta => {
    const next = episodes[episodeIndex + delta];
    if (!next) return;
    setEpisode(next);
    if (window.innerWidth < 980) {
      playerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const listItems = episodes.map(entry => ({
    id: entry.number,
    image: entry.still || detail?.poster || item?.poster || null,
    title: `E${entry.number} · ${entry.name}`,
    description: entry.overview || undefined,
    meta: entry.runtime ? `${entry.runtime} min` : entry.air_date || undefined
  }));

  return (
    <main className="watch view">
      <div className="shell watch__inner">
        <div className="watch__grid">
          <section className="watch__main">
            <div className="watch__player" ref={playerRef}>
              <StreamPlayer
                streams={streamData?.ok ? streamData.streams || [] : []}
                poster={poster}
                autoPlay={false}
                loading={
                  streamLoading ||
                  (isSeries && (season === null || !episode)) ||
                  (loading && !streamData?.ok)
                }
                emptyText={streamError || t('player.unavailable')}
                tmdbId={detail?.id ?? item?.id}
                imdbId={detail?.imdb_id || item?.imdb_id || null}
                mediaType={isSeries ? 'tv' : 'movie'}
                season={isSeries ? season : null}
                episode={isSeries && episode ? episode.number : null}
                audioLang={audioLang}
                availableLangs={AUDIO_LANGS}
                onAudioLangChange={code => {
                  setAudioLang(normalizeAudioLang(code));
                }}
                onReResolve={() => {
                  // Bust cache y vuelve a pedir streams sin salir de la ficha
                  const id = detail?.id ?? item?.id;
                  if (!id) return Promise.resolve();
                  const params = {
                    id,
                    media: isSeries ? 'tv' : (item?.media || 'movie'),
                    lang: audioLang,
                    nocache: '1',
                  };
                  if (item?.imdb_id || detail?.imdb_id) {
                    params.imdb = item?.imdb_id || detail?.imdb_id;
                  }
                  if (isSeries && season != null && episode?.number != null) {
                    params.season = season;
                    params.episode = episode.number;
                  }
                  setStreamLoading(true);
                  return api('/api/stream', params)
                    .then(data => {
                      setStreamData(data);
                      if (!data?.ok) {
                        setStreamError(t('player.unavailable'));
                      } else {
                        setStreamError('');
                      }
                    })
                    .catch(err => {
                      setStreamError(err?.message || t('player.unavailable'));
                    })
                    .finally(() => setStreamLoading(false));
                }}
              />
            </div>

            <header className="watch__head">
              <div className="watch__headtext">
                {isSeries && episode ? (
                  <span className="eyebrow">
                    {t('watch.seasonEpisode', { s: season, e: episode.number })}
                    {episode.air_date ? ` · ${episode.air_date}` : ''}
                  </span>
                ) : (
                  // El año ya vive en la fila de metadatos: repetirlo aquí
                  // justo debajo del reproductor se leía como un duplicado.
                  <span className="eyebrow">{kindText}</span>
                )}

                <h1 className="watch__title">{detail?.title || item?.title}</h1>
                {isSeries && episode ? <p className="watch__epname">{episode.name}</p> : null}

                <div className="watch__meta">
                  {rating > 0 ? (
                    <span className="watch__score">
                      <PeekRating
                        value={rating / 2}
                        count={5}
                        shape="star"
                        readOnly
                        size={15}
                        riseDuration={0}
                        activeColor="#f5b400"
                        idleColor="rgba(234, 242, 255, 0.22)"
                      />
                      <strong>{rating.toFixed(1)}</strong>
                    </span>
                  ) : (
                    <span className="watch__score">
                      <Star size={13} fill="currentColor" strokeWidth={0} />
                      {t('watch.noRating')}
                    </span>
                  )}
                  {year ? <span>{year}</span> : null}
                  {runtimeText ? <span>{runtimeText}</span> : null}
                  {episode?.runtime ? <span>{episode.runtime} min</span> : null}
                </div>
              </div>

              <div className="watch__actions">
                <button
                  type="button"
                  className={`watch__action${saved ? ' is-on' : ''}`}
                  onClick={() => onToggleSaved?.(item)}
                  aria-pressed={saved}
                >
                  {saved ? <Check size={16} /> : <Plus size={16} />}
                  {saved ? t('watch.inList') : t('watch.myList')}
                </button>
                <button type="button" className="watch__action" onClick={() => onOpenTitle?.(item)}>
                  <Info size={16} />
                  {t('watch.details')}
                </button>
                <button
                  type="button"
                  className="watch__action watch__action--download"
                  aria-label={t('watch.download')}
                  title={t('watch.download')}
                  disabled
                >
                  <Download size={16} />
                  {t('watch.download')}
                </button>
              </div>
            </header>

            {error ? (
              <div className="watch__notice" role="alert">
                {error}
              </div>
            ) : null}

            {audios.length || genres.length ? (
              <div className="watch__tags">
                {audios.map(audio => (
                  <span key={audio} className="tag tag--audio">
                    {t(`audio.${audio}`)}
                  </span>
                ))}
                {genres.slice(0, 5).map(genre => (
                  <span key={genre} className="tag">
                    {genre}
                  </span>
                ))}
              </div>
            ) : null}

            <p className="watch__desc" data-expanded={expanded ? '' : undefined}>
              {about || t('watch.emptyOverview')}
            </p>
            {long ? (
              <button type="button" className="watch__more" onClick={() => setExpanded(value => !value)}>
                {expanded ? t('common.less') : t('common.more')}
              </button>
            ) : null}

            {isSeries && episode ? (
              <div className="watch__naveps">
                <button type="button" onClick={() => jump(-1)} disabled={episodeIndex <= 0}>
                  <ChevronLeft size={16} />
                  {t('watch.prev')}
                </button>
                <span>{t('watch.of', { i: episodeIndex + 1, n: episodes.length })}</span>
                <button
                  type="button"
                  className="watch__next"
                  onClick={() => jump(1)}
                  disabled={episodeIndex < 0 || episodeIndex >= episodes.length - 1}
                >
                  {t('watch.next')}
                  <ChevronRight size={16} />
                </button>
              </div>
            ) : null}

            {detail?.review ? (
              <blockquote className="watch__review">
                <span className="watch__review-head">{t('watch.review', { author: detail.review.author || 'TMDB' })}</span>
                <span>{detail.review.content}</span>
              </blockquote>
            ) : null}
          </section>

          <aside className="watch__side">
            {/* Banners justo arriba de la tabla. Si la red no entrega nada,
                el bloque queda a cero y la tabla no se mueve. */}
            <div className="watch__ads">
              <AdSlot refreshMs={30000}
                src={AD_SLOTS.bannerPc}
                format="rect"
                media="(min-width: 901px)"
                label=""
              />
              <AdSlot refreshMs={30000}
                src={AD_SLOTS.videoMultitag}
                format="video"
                media="(min-width: 901px)"
                label=""
              />
              <AdSlot refreshMs={30000}
                src={AD_SLOTS.mobile}
                format="mobile"
                media="(max-width: 900px)"
                label=""
              />
            </div>
            {isSeries ? (
              <>
                <div className="watch__side-head">
                  <div>
                    <span className="eyebrow">{t('watch.episodes')}</span>
                    <h2>
                      {seasons.length
                        ? seasons.length === 1
                          ? t('title.seasonCountOne')
                          : t('title.seasonCount', { n: seasons.length })
                        : t('title.seasons')}
                    </h2>
                  </div>
                  {episodes.length ? (
                    <span className="watch__side-count">{t('watch.eps', { n: episodes.length })}</span>
                  ) : null}
                </div>

                <div className="watch__seasons">
                  {seasons.length ? (
                    seasons.length > 8 ? (
                      <div className="watch__picker" ref={pickerRef}>
                        <button
                          type="button"
                          className="watch__pick"
                          aria-expanded={seasonMenu}
                          aria-haspopup="listbox"
                          onClick={() => setSeasonMenu(value => !value)}
                        >
                          <span className="watch__pick-label">
                            {t('title.seasons')} <strong>{season ?? currentSeason?.number ?? 1}</strong>
                          </span>
                          <span className="watch__pick-count">
                            {currentSeason
                              ? t('watch.eps', { n: currentSeason.count })
                              : seasons.length === 1
                                ? t('title.seasonCountOne')
                                : t('title.seasonCount', { n: seasons.length })}
                          </span>
                          <ChevronDown size={15} className="watch__pick-caret" data-open={seasonMenu ? '' : undefined} />
                        </button>

                        {seasonMenu ? (
                          <div className="watch__pick-menu" role="listbox" aria-label={t('title.seasons')}>
                            {seasons.map(entry => (
                              <button
                                key={entry.number}
                                type="button"
                                role="option"
                                aria-selected={entry.number === season}
                                className="watch__pick-opt"
                                data-on={entry.number === season ? '' : undefined}
                                onClick={() => setSeason(entry.number)}
                              >
                                <strong>T{entry.number}</strong>
                                <small>{t('watch.eps', { n: entry.count })}</small>
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <RubberSegment
                        className="watch__segment"
                        items={seasons.map(entry => ({ value: String(entry.number), label: `T${entry.number}` }))}
                        value={season !== null ? String(season) : undefined}
                        onChange={value => setSeason(Number(value))}
                        trackColor="rgba(120, 175, 255, 0.08)"
                        thumbColor="#2f6bdd"
                        textColor="rgba(220, 235, 255, 0.62)"
                        activeTextColor="#ffffff"
                        size="md"
                        radius={11}
                        inset={3}
                        aria-label={t('title.seasons')}
                      />
                    )
                  ) : (
                    <span className="watch__hint">
                      <Loader2 className="spin" size={14} />
                      {t('watch.loadingSeasons')}
                    </span>
                  )}
                </div>

                {episodes.length ? (
                  <AnimatedList
                    key={`${season}-${listVersion}`}
                    items={listItems}
                    onItemSelect={(_, index) => {
                      listClick.current = true;
                      setEpisode(episodes[index]);
                    }}
                    initialSelectedIndex={Math.max(0, episodeIndex)}
                    selectOnHover={false}
                    animation="pop"
                    theme="dark"
                    frame={false}
                    width="100%"
                    maxHeight={470}
                    radius={12}
                    gap={6}
                    displayScrollbar={false}
                    className="watch__episodes"
                  />
                ) : (                    <p className="watch__hint">
                      <Loader2 className="spin" size={14} />
                      {t('watch.loadingEpisodes')}
                    </p>
                )}
              </>
            ) : (
              <>
                <div className="watch__side-head">
                  <div>
                    <span className="eyebrow">Kinora</span>
                    <h2>{t('watch.related')}</h2>
                  </div>
                </div>

                {relatedLoading && !related.length ? (                    <p className="watch__hint">
                      <Loader2 className="spin" size={14} />
                      {t('watch.loadingRelated')}
                    </p>
                ) : related.length ? (
                  <div className="watch__related">
                    {related.slice(0, 9).map(entry => (
                      <button
                        key={`${entry.media}-${entry.id}`}
                        type="button"
                        className="watch__mini"
                        onClick={() => onOpenTitle?.(entry)}
                      >
                        <span className="watch__mini-art">
                          {entry.poster ? <img src={entry.poster} alt="" loading="lazy" /> : null}
                        </span>
                        <span className="watch__mini-text">
                          <strong>{entry.title}</strong>
                          <small>
                            {entry.year ? `${entry.year} · ` : ''}
                            {entry.rating
                              ? `★ ${entry.rating.toFixed(1)}`
                              : entry.kind === 'tv'
                                ? t('home.series')
                                : entry.kind === 'anime'
                                  ? 'Anime'
                                  : t('home.movies')}
                          </small>
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="watch__hint">{t('watch.noRelated')}</p>
                )}
              </>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}