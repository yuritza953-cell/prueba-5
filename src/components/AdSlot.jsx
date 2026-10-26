import { useEffect, useRef, useState } from 'react';
import { injectAdScript, useAdConsent, useMediaQuery } from '../lib/ads';
import './Ads.css';

/**
 * Contenedor de un banner publicitario.
 *
 * Se monta colapsado (alto 0) y se expande solo cuando la red inserta una
 * creatividad con tamaño real. Si no hay anuncio —bloqueador, falta de
 * inventario o consentimiento rechazado— no reserva espacio ni mueve el
 * contenido.
 */
export default function AdSlot({
  src,
  format = 'banner',
  media = '',
  delay = 0,
  enabled = true,
  label = 'Publicidad',
  className = '',
  onFillChange
}) {
  const allowed = useAdConsent();
  const matches = useMediaQuery(media);
  const hostRef = useRef(null);
  const filledRef = useRef(false);
  const [filled, setFilled] = useState(false);

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
        setFill(false);
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

    // Algunos tags cambian el tamaño del iframe sin mutar el DOM: una lectura
    // periódica durante el primer minuto evita quedar con el hueco a cero.
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
      host.replaceChildren();
    };
  }, [allowed, matches, enabled, src, media, delay, onFillChange]);

  if (!enabled || !allowed || (media && !matches)) return null;

  return (
    <div
      className={`adslot adslot--${format}${filled ? ' is-filled' : ''}${className ? ` ${className}` : ''}`}
      data-ad-state={filled ? 'filled' : 'empty'}
      role="complementary"
      aria-label={label}
      aria-hidden={filled ? undefined : true}
    >
      <div ref={hostRef} className="adslot__host" />
    </div>
  );
}
