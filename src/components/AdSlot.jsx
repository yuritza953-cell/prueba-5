import { useEffect, useRef, useState } from 'react';
import { AD_REFRESH_MS, injectAdScript, useAdConsent, useMediaQuery } from '../lib/ads';
import './Ads.css';

/**
 * Contenedor de banner publicitario integrado al diseño Kinora.
 * - Panel glass con etiqueta "Publicidad"
 * - Se muestra sin exigir cookies
 * - Reinyecta el tag periódicamente para impresiones recurrentes
 */
export default function AdSlot({
  src,
  format = 'banner',
  media = '',
  delay = 0,
  enabled = true,
  label = '',
  className = '',
  refreshMs = AD_REFRESH_MS,
  onFillChange
}) {
  const allowed = useAdConsent(); // always true
  const matches = useMediaQuery(media);
  const hostRef = useRef(null);
  const filledRef = useRef(false);
  const [filled, setFilled] = useState(false);
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    if (!enabled || !allowed || !src || (media && !matches)) return undefined;
    if (!refreshMs || refreshMs < 15000) return undefined;
    const id = window.setInterval(() => setCycle(c => c + 1), refreshMs);
    return () => window.clearInterval(id);
  }, [enabled, allowed, src, media, matches, refreshMs]);

  useEffect(() => {
    if (!enabled || !allowed || !src || (media && !matches)) return undefined;
    const host = hostRef.current;
    if (!host) return undefined;

    let disposed = false;
    let timer = 0;
    let interval = 0;
    let mutation = null;
    let resize = null;

    const setFill = next => {
      if (disposed || next === filledRef.current) return;
      filledRef.current = next;
      setFilled(next);
      onFillChange?.(next);
    };

    const measure = () => {
      if (disposed) return;
      const unit = [...host.children].find(node => node.tagName !== 'SCRIPT');
      if (!unit) {
        // scripts only — still consider "filled" to keep panel after first paint
        if (host.querySelector('iframe, img, ins')) setFill(true);
        return;
      }
      const rect = unit.getBoundingClientRect();
      const height = Math.max(unit.scrollHeight || 0, rect.height || 0);
      const width = Math.max(unit.scrollWidth || 0, rect.width || 0);
      setFill(height >= 12 && width >= 12);
    };

    host.replaceChildren();
    filledRef.current = false;
    setFilled(false);

    mutation = new MutationObserver(measure);
    mutation.observe(host, { childList: true, subtree: true, attributes: true });
    resize = new ResizeObserver(measure);
    resize.observe(host);

    const mount = () => {
      if (disposed) return;
      injectAdScript(host, src);
      window.requestAnimationFrame(measure);
    };

    if (delay > 0) timer = window.setTimeout(mount, delay);
    else mount();

    let ticks = 0;
    interval = window.setInterval(() => {
      ticks += 1;
      measure();
      if (ticks > 60) window.clearInterval(interval);
    }, 1000);

    return () => {
      disposed = true;
      window.clearTimeout(timer);
      window.clearInterval(interval);
      mutation?.disconnect();
      resize?.disconnect();
    };
  }, [enabled, allowed, src, media, matches, delay, cycle, onFillChange]);

  if (!enabled || !allowed || (media && !matches)) return null;

  return (
    <aside
      className={`adslot adslot--panel adslot--${format}${filled ? ' is-filled' : ''}${className ? ` ${className}` : ''}`}
      data-format={format}
      aria-label={label}
    >
      <div className="adslot__chrome">
        <span className="adslot__badge">{label}</span>
      </div>
      <div className="adslot__body" ref={hostRef} />
    </aside>
  );
}