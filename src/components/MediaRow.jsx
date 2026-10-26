import { ArrowRight } from 'lucide-react';
import ChromaGrid from './ChromaGrid';
import { toChromaItem } from '../lib/media';
import { useT } from '../i18n';
import './MediaRow.css';

export default function MediaRow({ title, items = [], onOpen, onSeeAll, limit = 8, loading = false, count }) {
  const t = useT();
  const kindOf = item => (item?.kind === 'tv' ? t('home.series') : item?.kind === 'anime' ? 'Anime' : t('home.movies'));
  const list = items.slice(0, limit).map((item, index) => toChromaItem(item, index, kindOf(item)));

  return (
    <section className="mrow">
      <header className="mrow__head">
        <h2 className="mrow__title">
          {title}
          {count ? <span className="mrow__count">{count}</span> : null}
        </h2>
        {onSeeAll ? (
          <button type="button" className="mrow__all" onClick={onSeeAll}>
            {t('common.more')}
            <ArrowRight size={15} />
          </button>
        ) : null}
      </header>

      {loading ? (
        <div className="mrow__skeleton-grid" aria-busy="true" aria-label={t('common.loading')}>
          {Array.from({ length: limit }, (_, index) => (
            <span key={index} className="mrow__skeleton" aria-hidden="true" />
          ))}
        </div>
      ) : list.length ? (
        <ChromaGrid
          items={list}
          theme="site"
          columns={8}
          minCardWidth={120}
          aspectRatio="2 / 3"
          cardRadius={16}
          radius={260}
          gap={14}
          grayscale={0}
          dim={0.04}
          onSelect={onOpen}
        />
      ) : null}
    </section>
  );
}
