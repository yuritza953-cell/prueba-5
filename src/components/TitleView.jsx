import { Bookmark, Check, ExternalLink, Loader2, Play } from 'lucide-react';
import PeekRating from './PeekRating';
import MediaRow from './MediaRow';

import { useT } from '../i18n';
import './TitleView.css';

const runtimeOf = (detail, t) => {
  if (detail?.runtime) return `${detail.runtime} min`;
  const seasons = detail?.seasons?.length ?? 0;
  if (seasons) return seasons === 1 ? t('title.seasonCountOne') : t('title.seasonCount', { n: seasons });
  return '';
};

export default function TitleView({
  item,
  detail,
  loading = false,
  error = '',
  related = [],
  relatedLoading = false,
  shelves = [],
  shelvesLoading = false,
  saved = false,
  onToggleSaved,
  onPlay,
  onOpen,
  onRetry
}) {
  const t = useT();
  const isSeries = (item?.media ?? detail?.kind) === 'tv';
  const title = detail?.title || item?.title || '';
  const backdrop = detail?.backdrop || item?.backdrop || detail?.poster || item?.poster;
  const poster = detail?.poster || item?.poster;
  const rating = Number(detail?.rating ?? item?.rating ?? 0);
  const genres = detail?.genres ?? [];
  const audios = detail?.audio ?? item?.audio ?? [];
  const seasons = detail?.seasons ?? [];
  const overview = detail?.overview || item?.overview || '';
  const kindText = item?.kind === 'tv' ? t('home.series') : item?.kind === 'anime' ? 'Anime' : t('home.movies');
  const meta = [detail?.year || item?.year, kindText, runtimeOf(detail, t)].filter(Boolean);
  const votes = detail?.votes ?? item?.votes;

  return (
    <main className="titleview view">
      <div className="titleview__hero">
        {backdrop ? <div className="titleview__bg" style={{ backgroundImage: `url(${backdrop})` }} aria-hidden="true" /> : null}
        <div className="titleview__veil" aria-hidden="true" />

        <div className="shell titleview__inner">
          <div className="titleview__head">
            <div className="titleview__poster">
              {poster ? <img src={poster} alt={title} /> : <span>{title.slice(0, 2)}</span>}
            </div>

            <div className="titleview__lead">
              <span className="eyebrow">
                {kindText}
                {isSeries && seasons.length ? ` · ${seasons.length === 1 ? t('title.seasonCountOne') : t('title.seasonCount', { n: seasons.length })}` : ''}
              </span>
              <h1 className="titleview__title">{title}</h1>

              <div className="titleview__meta">
                <span>{meta.join(' · ')}</span>
                {rating > 0 ? (
                  <span className="titleview__score">
                    <PeekRating
                      value={rating / 2}
                      count={5}
                      shape="star"
                      readOnly
                      size={17}
                      riseDuration={0}
                      activeColor="#f5b400"
                      idleColor="rgba(234, 242, 255, 0.22)"
                    />
                    <strong>{rating.toFixed(1)}</strong>
                    {votes ? <em>{t('title.votes', { n: Number(votes).toLocaleString() })}</em> : null}
                  </span>
                ) : null}
              </div>

              {genres.length || audios.length ? (
                <div className="titleview__tags">
                  {genres.slice(0, 5).map(genre => (
                    <span key={genre} className="tag">
                      {genre}
                    </span>
                  ))}
                  {audios.map(audio => (
                    <span key={audio} className="tag tag--audio">
                      {t(`audio.${audio}`)}
                    </span>
                  ))}
                </div>
              ) : null}

              {detail?.tagline ? <p className="titleview__tagline">“{detail.tagline}”</p> : null}

              <div className="titleview__actions">
                <button type="button" className="btn btn--play" onClick={() => onPlay?.(item)}>
                  <Play size={16} fill="currentColor" strokeWidth={0} />
                  {t('title.play')}
                </button>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => onToggleSaved?.(item)}
                  aria-pressed={saved}
                >
                  {saved ? <Check size={16} /> : <Bookmark size={16} />}
                  {saved ? t('title.inList') : t('title.myList')}
                </button>
                {detail?.url ? (
                  <a className="btn btn--ghost" href={detail.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink size={15} />
                    TMDB
                  </a>
                ) : null}
              </div>

              {error ? (
                <div className="titleview__error" role="alert">
                  <span>{error}</span>
                  {onRetry ? (
                    <button type="button" onClick={onRetry}>
                      <Loader2 size={14} />
                      {t('title.retry')}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className="shell titleview__content">
        <div className="titleview__main">
          <section className="titleview__block">
            <h2>{t('title.synopsis')}</h2>
            {loading && !overview ? (
              <div className="titleview__lines" aria-busy="true">
                <span />
                <span />
                <span />
              </div>
            ) : (
              <p>{overview || t('title.emptyOverview')}</p>
            )}
          </section>

          {detail?.review ? (
            <blockquote className="titleview__review">
              <span className="titleview__review-head">{t('watch.review', { author: detail.review.author || 'TMDB' })}</span>
              <span>{detail.review.content}</span>
            </blockquote>
          ) : null}

          {isSeries && seasons.length ? (
            <section className="titleview__block">
              <div className="titleview__block-head">
                <h2>{t('title.seasons')}</h2>
                <span>{seasons.length === 1 ? t('title.seasonCountOne') : t('title.seasonCount', { n: seasons.length })}</span>
              </div>
              <div className="titleview__seasons">
                {seasons.map(season => (
                  <button
                    key={season.number}
                    type="button"
                    className="titleview__season"
                    onClick={() => onPlay?.(item, { season: season.number })}
                    aria-label={`${t('title.play')} · ${t('title.seasons')} ${season.number}`}
                  >
                    <span className="titleview__season-num">T{season.number}</span>
                    <span className="titleview__season-count">
                      {season.count} {t('watch.episodes')}
                    </span>
                    <span className="titleview__season-play">
                      <Play size={13} fill="currentColor" strokeWidth={0} />
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </div>

      {related.length || relatedLoading ? (
        <div className="shell titleview__related">
          <MediaRow title={t('title.related')} items={related} loading={relatedLoading && !related.length} onOpen={onOpen} limit={10} />
        </div>
      ) : null}

      {(shelves.length || shelvesLoading) ? (
        <div className="shell titleview__shelves">
          {shelvesLoading && !shelves.length ? (
            <MediaRow title="…" items={[]} loading onOpen={onOpen} limit={8} />
          ) : (
            shelves.map(row => (
              <MediaRow
                key={row.key || row.title}
                title={row.title}
                items={row.items || []}
                onOpen={onOpen}
                limit={12}
              />
            ))
          )}
        </div>
      ) : null}
    </main>
  );
}