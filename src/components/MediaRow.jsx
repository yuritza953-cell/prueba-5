import { useRef, useState, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, ArrowRight } from 'lucide-react';
import ChromaGrid from './ChromaGrid';
import { toChromaItem } from '../lib/media';
import { useT } from '../i18n';
import './MediaRow.css';

export default function MediaRow({
  title,
  items = [],
  onOpen,
  onSeeAll,
  limit = 12,
  loading = false,
  count,
  /** 0 = sin anuncios en la fila (recomendado en ficha / home rows) */
  adEvery = 0,
}) {
  const t = useT();
  const trackRef = useRef(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);

  const kindOf = item =>
    item?.kind === 'tv' ? t('home.series') : item?.kind === 'anime' ? 'Anime' : t('home.movies');
  const list = items.slice(0, limit).map((item, index) => toChromaItem(item, index, kindOf(item)));

  const updateNav = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth - 4;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft < max);
  }, []);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return undefined;
    updateNav();
    el.addEventListener('scroll', updateNav, { passive: true });
    const ro = new ResizeObserver(updateNav);
    ro.observe(el);
    return () => {
      el.removeEventListener('scroll', updateNav);
      ro.disconnect();
    };
  }, [list.length, loading, updateNav]);

  const scrollByDir = dir => {
    const el = trackRef.current;
    if (!el) return;
    const step = Math.max(el.clientWidth * 0.75, 240);
    el.scrollBy({ left: dir * step, behavior: 'smooth' });
  };

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
          {Array.from({ length: Math.min(limit, 8) }, (_, index) => (
            <span key={index} className="mrow__skeleton" aria-hidden="true" />
          ))}
        </div>
      ) : list.length ? (
        <div className="mrow__rail">
          <button
            type="button"
            className="mrow__nav mrow__nav--prev"
            aria-label="Anterior"
            disabled={!canPrev}
            onClick={() => scrollByDir(-1)}
          >
            <ChevronLeft size={22} />
          </button>
          <div className="mrow__track" ref={trackRef}>
            <ChromaGrid
              items={list}
              theme="site"
              columns={list.length}
              minCardWidth={140}
              aspectRatio="2 / 3"
              cardRadius={16}
              radius={260}
              gap={14}
              grayscale={0}
              dim={0.04}
              onSelect={onOpen}
              adEvery={adEvery}
              className="mrow__grid"
            />
          </div>
          <button
            type="button"
            className="mrow__nav mrow__nav--next"
            aria-label="Siguiente"
            disabled={!canNext}
            onClick={() => scrollByDir(1)}
          >
            <ChevronRight size={22} />
          </button>
        </div>
      ) : null}
    </section>
  );
}