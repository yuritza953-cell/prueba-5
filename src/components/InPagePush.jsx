import { useEffect } from 'react';
import { injectAdScript, useAdConsent } from '../lib/ads';

const SESSION_KEY = 'kinora:inpage-push';

/**
 * In-page push (HilltopAds).
 *
 * El tag no acepta que le digamos dónde dibujar: crea su propia notificación
 * con `position: fixed` (arriba y a todo el ancho en Android, abajo a la
 * derecha en escritorio) y la cuelga del body. Por eso la "zona estratégica"
 * no puede ser un hueco del layout, sino el momento y la pantalla en que se
 * carga:
 *
 *  - nunca en /watch: taparía los controles del reproductor o la barra fija;
 *  - una sola vez por sesión (ni al navegar entre fichas ni al recargar la SPA);
 *  - a los 25 s de lectura, o al primer scroll real si llega antes;
 *  - jamás sin consentimiento de publicidad (Política de Privacidad §8).
 *
 * Con esas tres reglas el formato sigue existiendo, pero deja de interrumpir
 * la entrada a la web y la reproducción.
 */
export default function InPagePush({ src, enabled = true, delay = 25000 }) {
  const allowed = useAdConsent();

  useEffect(() => {
    if (!enabled || !allowed || !src || typeof window === 'undefined') return undefined;

    let shown = false;
    try {
      if (window.sessionStorage.getItem(SESSION_KEY) === '1') return undefined;
    } catch {
      /* almacenamiento bloqueado: el guardia en memoria sigue valiendo */
    }

    let timer = 0;
    let disposed = false;

    const stop = () => {
      window.clearTimeout(timer);
      window.removeEventListener('scroll', onScroll);
    };

    const fire = () => {
      if (disposed || shown) return;
      shown = true;
      try {
        window.sessionStorage.setItem(SESSION_KEY, '1');
      } catch {
        /* sin almacenamiento: se muestra igual */
      }
      stop();
      injectAdScript(document.body, src);
    };

    // "Primer scroll real": media pantalla o 420 px, lo que llegue antes. Con
    // el 80 % de una ventana el umbral es inalcanzable en páginas cortas.
    function onScroll() {
      if (window.scrollY > Math.min(window.innerHeight * 0.6, 420)) fire();
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    timer = window.setTimeout(fire, delay);

    return () => {
      disposed = true;
      stop();
    };
  }, [allowed, enabled, src, delay]);

  return null;
}
