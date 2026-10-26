import { Loader2, Sparkles } from 'lucide-react';
import ChromaGrid from './ChromaGrid';
import { toChromaItem } from '../lib/media';
import { useT } from '../i18n';
import './BrowseView.css';

export default function BrowseView({
  eyebrow,
  title,
  description,
  count,
  items = [],
  loading = false,
  error = '',
  onOpen,
  onLoadMore,
  hasMore = false,
  loadingMore = false,
  emptyTitle,
  emptyText,
  suggestions = [],
  onSuggestion,
  action = null
}) {
  const t = useT();
  const kindOf = item => (item?.kind === 'tv' ? t('home.series') : item?.kind === 'anime' ? 'Anime' : t('home.movies'));
  const cards = items.map((item, index) => toChromaItem(item, index, kindOf(item)));

  return (
    <main className="browse view">
      <div className="shell">
        <header className="browse__head">
          <span className="eyebrow">{eyebrow ?? t('search.eyebrow')}</span>
          <h1 className="browse__title">{title}</h1>
          {description ? <p className="browse__desc">{description}</p> : null}

          <div className="browse__meta">
            {typeof count === 'number' ? (
              <span className="browse__count">{count === 1 ? t('browse.countOne') : t('browse.count', { n: count })}</span>
            ) : null}
            {action}
          </div>
        </header>

        {error ? (
          <div className="browse__notice" role="alert">
            <span>{error}</span>
          </div>
        ) : null}

        {loading ? (
          <div className="browse__skeleton" aria-busy="true" aria-label={t('common.loading')}>
            {Array.from({ length: 12 }, (_, index) => (
              <span key={index} />
            ))}
          </div>
        ) : cards.length ? (
          <div className="browse__grid">
            <ChromaGrid
              items={cards}
              theme="site"
              columns={6}
              minCardWidth={148}
              aspectRatio="2 / 3"
              cardRadius={16}
              radius={260}
              gap={14}
              grayscale={0}
              dim={0.04}
              onSelect={onOpen}
            />
          </div>
        ) : (
          !error && (
            <div className="browse__empty">
              <span className="browse__empty-icon">
                <Sparkles size={22} />
              </span>
              <h2>{emptyTitle ?? t('browse.emptyTitle')}</h2>
              <p>{emptyText ?? t('browse.emptyText')}</p>
              {suggestions.length ? (
                <div className="browse__suggestions">
                  {suggestions.map(text => (
                    <button key={text} type="button" onClick={() => onSuggestion?.(text)}>
                      {text}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          )
        )}

        {hasMore ? (
          <div className="browse__more">
            <button type="button" className="btn btn--info" onClick={onLoadMore} disabled={loadingMore}>
              {loadingMore ? <Loader2 className="spin" size={16} /> : null}
              {loadingMore ? t('browse.loadingMore') : t('browse.loadMore')}
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}
