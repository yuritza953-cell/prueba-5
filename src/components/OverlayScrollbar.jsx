'use client';

import { useEffect, useRef, useState } from 'react';
import './OverlayScrollbar.css';

// Scrollbar propio: el nativo esta oculto (no redimensiona la pagina) y este
// pulgar flota sobre el borde derecho, visible solo mientras hay movimiento.
export default function OverlayScrollbar() {
  const thumbRef = useRef(null);
  const [enabled, setEnabled] = useState(false);
  const [visible, setVisible] = useState(false);
  const [present, setPresent] = useState(false);

  // En celular/pantalla tactil no se pinta nada.
  useEffect(() => {
    const query = window.matchMedia('(hover: hover) and (pointer: fine)');
    const sync = () => setEnabled(query.matches);
    sync();
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    const thumb = thumbRef.current;
    if (!thumb) return undefined;

    let raf = 0;
    let hideTimer = 0;
    let dragging = false;

    const measure = () => {
      raf = 0;
      const doc = document.documentElement;
      const view = window.innerHeight;
      const total = doc.scrollHeight;
      const scrollable = total - view;
      if (scrollable <= 8) {
        setPresent(false);
        return;
      }
      const height = Math.max(36, (view / total) * view);
      const max = view - height - 8;
      const top = 4 + (window.scrollY / scrollable) * max;
      thumb.style.height = `${height.toFixed(1)}px`;
      thumb.style.transform = `translate3d(0, ${top.toFixed(1)}px, 0)`;
      setPresent(true);
    };

    const schedule = () => {
      if (!raf) raf = window.requestAnimationFrame(measure);
    };

    const wake = () => {
      schedule();
      setVisible(true);
      window.clearTimeout(hideTimer);
      hideTimer = window.setTimeout(() => setVisible(false), 950);
    };

    const onScroll = () => {
      schedule();
      if (dragging) return;
      wake();
    };

    const onResize = () => {
      schedule();
      wake();
    };

    const onDown = e => {
      dragging = true;
      thumb.classList.add('is-dragging');
      thumb.setPointerCapture(e.pointerId);
      e.preventDefault();
    };

    const onMove = e => {
      if (!dragging) return;
      const doc = document.documentElement;
      const view = window.innerHeight;
      const scrollable = doc.scrollHeight - view;
      const bar = thumb.getBoundingClientRect();
      const usable = view - bar.height - 8;
      const frac = Math.min(1, Math.max(0, (e.clientY - 4 - bar.height / 2) / Math.max(1, usable)));
      window.scrollTo({ top: frac * scrollable });
    };

    const onUp = e => {
      if (!dragging) return;
      dragging = false;
      thumb.classList.remove('is-dragging');
      try {
        thumb.releasePointerCapture(e.pointerId);
      } catch {}
      wake();
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onResize);
    thumb.addEventListener('pointerdown', onDown);
    thumb.addEventListener('pointermove', onMove);
    thumb.addEventListener('pointerup', onUp);
    thumb.addEventListener('pointercancel', onUp);
    measure();
    wake();

    return () => {
      window.clearTimeout(hideTimer);
      if (raf) window.cancelAnimationFrame(raf);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onResize);
      thumb.removeEventListener('pointerdown', onDown);
      thumb.removeEventListener('pointermove', onMove);
      thumb.removeEventListener('pointerup', onUp);
      thumb.removeEventListener('pointercancel', onUp);
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <div className={`ovsb${visible && present ? ' is-visible' : ''}`} aria-hidden="true">
      <span ref={thumbRef} className="ovsb__thumb" />
    </div>
  );
}
