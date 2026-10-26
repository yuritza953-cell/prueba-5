import { useEffect, useState } from 'react';
import { canShowPersonalizedAds } from './cookies';

/**
 * Inventario publicitario de Kinora.
 * Los creativos se sirven desde las redes externas; aquí solo viven las URLs
 * de los tags para poder cargarlos de forma perezosa y con consentimiento.
 */
export const AD_SLOTS = Object.freeze({
  bannerPc: 'https://shameful-farm.com/bYX-Vbs.dBGLlj0/Y-W/cr/TeImk9kuuZ/UHlskcPkTfcC1oNVTEI_zqMjDnUvteNxzoUE1NMJjqMnwZOkQY',
  mobile: 'https://shameful-farm.com/bnXxV.shduGxli0NYHWrcU/geBmC9/uXZMUSlJktPrTJcr1vNWT/IDyzO/DGUnteNbz/U/1LM-jmIX4gO/QH',
  inPagePush: 'https://shameful-farm.com/baXsV/s.dkGplU0/YZW_cA/JeFmj9Ku/Z/UJlokUPnTMcI1VNxTZI/ziMgjAElt/NfzRU/1oMLjeMhyHN/QD',
  videoMultitag: 'https://shameful-farm.com/bFX.V/s/dWGllV0bYHWycO/CewmQ9lurZ/UilhkEPHTicE1/NyTIIRzjNyDBUKtLNLzFUq1uMbjWMO0/O-QF'
});

/** Tag VAST del preroll de 5 s del reproductor (HilltopAds). */
export const PREROLL_VAST = 'https://windy-imagination.com/dcm.Fjzed_GUNDvAZJGYUc/Eetmj9XuvZ/UklsksPxTPcN1jNrTNIcyINNzUcKtoN/z-Uc1MMejGI/4fM_Qi';

/** ¿El usuario autorizó publicidad no esencial? Reacciona al aviso de cookies. */
export function useAdConsent() {
  const [allowed, setAllowed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return canShowPersonalizedAds();
  });

  useEffect(() => {
    const sync = () => setAllowed(canShowPersonalizedAds());
    window.addEventListener('kinora:consent', sync);
    return () => window.removeEventListener('kinora:consent', sync);
  }, []);

  return allowed;
}

/** Media query reactiva; segura en el primer render (SSR / build). */
export function useMediaQuery(query = '') {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || !query) return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (!query || typeof window === 'undefined') return undefined;
    const mql = window.matchMedia(query);
    const sync = () => setMatches(mql.matches);
    sync();
    mql.addEventListener?.('change', sync);
    return () => mql.removeEventListener?.('change', sync);
  }, [query]);

  return matches;
}

/**
 * Inserta el tag tal como lo entrega la red: un script puente que se inserta
 * en el contenedor para que el script externo encuentre su punto de anclaje.
 */
export function injectAdScript(host, src, settings = {}) {
  if (!host || !src) return;
  const inline = document.createElement('script');
  inline.setAttribute('data-kinora-ad-tag', '1');
  inline.textContent = `(function(settings){var d=document,s=d.createElement('script'),l=d.currentScript;s.settings=settings||{};s.src=${JSON.stringify(
    src
  )};s.async=true;s.referrerPolicy='no-referrer-when-downgrade';l.parentNode.insertBefore(s,l);})(${JSON.stringify(
    settings || {}
  )});`;
  host.appendChild(inline);
}

/** Baliza de impresión del VAST (no necesita CORS). */
export function fireAdPixel(url) {
  if (!url || typeof window === 'undefined') return;
  try {
    const img = new Image();
    img.referrerPolicy = 'no-referrer-when-downgrade';
    img.src = url;
  } catch {
    /* el bloqueador de anuncios puede impedirlo */
  }
}

const parseMedia = node => ({
  url: (node.textContent || '').trim(),
  type: (node.getAttribute('type') || '').toLowerCase(),
  width: Number(node.getAttribute('width')) || 0,
  height: Number(node.getAttribute('height')) || 0
});

/**
 * Descarga y resuelve el primer anuncio lineal del tag VAST.
 * Devuelve el MP4/WebM, el click-through y la baliza de impresión.
 */
export async function loadVastPreroll({ signal, viewportWidth = 0 } = {}) {
  const response = await fetch(PREROLL_VAST, {
    signal,
    credentials: 'omit',
    cache: 'no-store'
  });
  if (!response.ok) throw new Error(`VAST HTTP ${response.status}`);

  const xml = await response.text();
  if (!xml.includes('<VAST') && !xml.includes('<vast')) {
    throw new Error('VAST vacío');
  }

  const doc = new DOMParser().parseFromString(xml, 'text/xml');
  const ad = [...doc.querySelectorAll('Ad')].find(node => node.querySelector('MediaFile'));
  if (!ad) throw new Error('VAST sin creatividades');

  const target = viewportWidth > 0 && viewportWidth < 760 ? 360 : 720;
  const media = [...ad.querySelectorAll('MediaFile')]
    .map(parseMedia)
    .filter(item => item.url && (!item.type || item.type.startsWith('video/')))
    .sort((a, b) => {
      const aMp4 = a.type === 'video/mp4' || /\.mp4($|\?)/i.test(a.url);
      const bMp4 = b.type === 'video/mp4' || /\.mp4($|\?)/i.test(b.url);
      if (aMp4 !== bMp4) return aMp4 ? -1 : 1;
      return Math.abs(a.height - target) - Math.abs(b.height - target);
    })[0];

  if (!media) throw new Error('VAST sin media reproducible');

  return {
    mediaUrl: media.url,
    clickThrough: (ad.querySelector('ClickThrough')?.textContent || '').trim(),
    impression: (ad.querySelector('Impression')?.textContent || '').trim(),
    duration: (ad.querySelector('Duration')?.textContent || '').trim()
  };
}
