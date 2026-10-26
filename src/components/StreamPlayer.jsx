/**
 * Player HLS/MP4 con hls.js + controles glass propios.
 * (Video.js VHS marcaba VOD como LIVE y no pedía segmentos.)
 */
'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Captions,
  Check,
  Maximize,
  Minimize,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Languages,
  Settings2,
  Volume2,
  VolumeX
} from 'lucide-react';
import './StreamPlayer.css';
import { randomVerse } from '../lib/verses';
import { getCachedSub, setCachedSub } from '../lib/subCache';
import { canShowPersonalizedAds } from '../lib/cookies.js';
import { fireAdPixel, loadVastPreroll } from '../lib/ads';
import { useT } from '../i18n';
import { AUDIO_LANGS as DEFAULT_AUDIO_LANGS } from '../lib/audioLangs';

const HLS_JS = 'https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js';
// Pre-carga hls.js inmediatamente al importar el módulo (sin esperar al click de play)
let hlsPromise = null;
if (typeof window !== 'undefined') {
  // Lanzar la carga en background para que esté lista cuando el usuario pulse Play
  setTimeout(() => { try { loadHls(); } catch(_){} }, 0);
}

function loadHls() {
  if (window.Hls) return Promise.resolve(window.Hls);
  if (hlsPromise) return hlsPromise;
  hlsPromise = new Promise((resolve, reject) => {
    const tag = document.createElement('script');
    tag.src = HLS_JS;
    tag.async = true;
    tag.onload = () => (window.Hls ? resolve(window.Hls) : reject(new Error('Hls missing')));
    tag.onerror = () => reject(new Error('Hls load fail'));
    document.head.appendChild(tag);
  });
  return hlsPromise;
}

function isHls(url, type) {
  const t = (type || '').toLowerCase();
  if (t === 'mp4' || t === 'video/mp4') return false;
  const low = (url || '').toLowerCase().split('?')[0];
  if (low.includes('.mp4')) return false;
  if (low.includes('.m3u8')) return true;
  // proxy_url relativo sin extensión: confiar en type (default hls)
  return t === 'hls' || t === '' || t === 'application/x-mpegurl';
}

function streamsKey(streams) {
  if (!streams?.length) return '';
  return streams.map(s => `${s.proxy_url || ''}|${s.url || ''}`).join(';;');
}

function fmt(s) {
  if (!Number.isFinite(s) || s < 0) s = 0;
  const total = Math.floor(s);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

const isTyping = target => {
  if (!target) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
};

export default function StreamPlayer({
  streams = [],
  poster = '',
  autoPlay = false,
  emptyText = '',
  loading = false,
  tmdbId = null,
  imdbId = null,
  mediaType = 'movie',
  season = null,
  episode = null,
  audioLang = 'es-MX',
  availableLangs = null,
  onAudioLangChange = null
}) {
  const t = useT();
  const videoRef = useRef(null);
  const rootRef = useRef(null);
  const hlsRef = useRef(null);
  const barRef = useRef(null);
  const attemptRef = useRef({ index: 0, usedProxy: false });
  const dragRef = useRef(false);
  const subUrlRef = useRef(null);
  const key = streamsKey(streams);

  const [failed, setFailed] = useState('');
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(0.9);
  const [full, setFull] = useState(false);
  const [ui, setUi] = useState(true);
  const hideTimer = useRef(0);
  const playingRef = useRef(false);

  // Subtítulos (OpenSubtitles vía backend)
  const [subOpen, setSubOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const [subLoading, setSubLoading] = useState(false);
  const [subList, setSubList] = useState([]);
  const [subError, setSubError] = useState('');
  const [activeSub, setActiveSub] = useState(null); // { file_id, label, language }
  const canSubs = Boolean(tmdbId || imdbId);
  const [userStarted, setUserStarted] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const pauseAtRef = useRef(0);
  const resumePosRef = useRef(0);
  const recoverTriesRef = useRef(0);
  const userStartedRef = useRef(false);
  const [verse] = useState(() => randomVerse());
  // null | 'ad' — anuncio antes de reproducir (Google AdSense slot)
  const [adPhase, setAdPhase] = useState(null);
  const [adLeft, setAdLeft] = useState(5);
  const adTimerRef = useRef(0);
  // Creatividad del preroll (VAST). null = cargando / sin relleno.
  const [preroll, setPreroll] = useState(null);
  const [adStatus, setAdStatus] = useState('idle');
  const adVideoRef = useRef(null);

  // Calidad adaptativa (niveles de hls.js)
  const [qualityOpen, setQualityOpen] = useState(false);
  const [levels, setLevels] = useState([]);
  const [quality, setQuality] = useState(-1);

  // Doble toque para saltar ±10 s
  const tapRef = useRef({ time: 0, x: 0 });
  const singleTapRef = useRef(0);
  const flashTimerRef = useRef(0);
  const [flash, setFlash] = useState(null);
  const hoveringRef = useRef(false);
  // Ref de buffering para usarlo dentro de closures sin capturar state stale.
  const bufferingRef = useRef(false);
  // Estado de los controles en el instante del toque: decide si el toque
  // reproduce/pausa o solo los muestra (móvil).
  const uiRef = useRef(ui);
  const surfaceVisibleRef = useRef(true);

  playingRef.current = playing;
  uiRef.current = ui;

  const destroyHls = () => {
    if (hlsRef.current) {
      try {
        hlsRef.current.destroy();
      } catch {
        /* ignore */
      }
      hlsRef.current = null;
    }
  };

  const pickSrc = useCallback(list => {
    const { index, usedProxy } = attemptRef.current;
    if (index >= list.length) return null;
    const entry = list[index];
    // Worker resolve: el player pide JSON y luego usa la URL limpia
    if (entry.resolve_url && !entry.url && !entry.proxy_url) {
      return { src: entry.resolve_url, type: 'resolve', entry };
    }
    const hasProxy = Boolean(entry.proxy_url);
    let src;
    if (hasProxy && !usedProxy) {
      src = entry.proxy_url;
    } else if (entry.direct !== false && entry.url) {
      src = entry.url;
    } else if (hasProxy && usedProxy) {
      return null;
    } else {
      src = entry.url;
    }
    if (!src) return null;
    return { src, type: entry.type, entry };
  }, []);

  const advance = useCallback(list => {
    const { index, usedProxy } = attemptRef.current;
    const entry = list[index];
    // Si hay proxy y aún no se usó, marcar usedProxy (próximo intento: direct solo si allowed)
    if (!usedProxy && entry?.proxy_url && entry?.direct !== false && entry?.url) {
      attemptRef.current = { index, usedProxy: true };
    } else {
      attemptRef.current = { index: index + 1, usedProxy: false };
    }
  }, []);

  useEffect(() => {
    attemptRef.current = { index: 0, usedProxy: false };
    setFailed('');
    setReady(false);
    setPlaying(false);
    setCurrent(0);
    setDuration(0);
    setLevels([]);
    setQuality(-1);
    setQualityOpen(false);
    destroyHls();

    const video = videoRef.current;
    if (video) {
      video.removeAttribute('src');
      video.load();
    }

    if (!streams?.length || loading) return undefined;

    let cancelled = false;
    const list = streams;

    const tryLoad = async () => {
      const chosen = pickSrc(list);
      if (!chosen) {
        if (!cancelled) setFailed(emptyText || t('player.unavailable'));
        return;
      }

      const video = videoRef.current;
      if (!video || cancelled) return;

      let playSrc = chosen.src;
      let playType = chosen.type;

      // Worker solo resolvió: JSON con URL limpia → el browser baja el media
      if (playType === 'resolve' || chosen.entry?.resolve_url) {
        try {
          const res = await fetch(chosen.entry.resolve_url || playSrc);
          const data = await res.json();
          const first = data?.streams?.[0];
          if (!data?.ok || !first?.url) {
            console.warn('[resolve] fail', data);
            advance(list);
            if (!cancelled) tryLoad();
            return;
          }
          playSrc = first.url;
          playType = first.type || 'hls';
          // Mantener host exacto del Worker; quitar r=e si parece modo referer
          try {
            const u = new URL(playSrc);
            if (u.searchParams.get('r') === 'e') {
              u.searchParams.delete('r');
              playSrc = u.toString();
            }
          } catch {
            /* keep original */
          }
          // Candidatos extra del worker como siguientes intentos
          if (Array.isArray(data.streams) && data.streams.length > 1) {
            for (let i = 1; i < data.streams.length; i++) {
              const s = data.streams[i];
              if (s?.url) list.push({ url: s.url, type: s.type || 'hls', direct: true, ref: s.ref || '' });
            }
          }
        } catch (err) {
          console.warn('[resolve] error', err);
          advance(list);
          if (!cancelled) tryLoad();
          return;
        }
      }

      const useHls = isHls(playSrc, playType);

      if (useHls) {
        try {
          const Hls = await loadHls();
          if (cancelled) return;

          if (Hls.isSupported()) {
            destroyHls();
            // URL exacta del Worker (no reescribir host). Referer vacío / vimeos.
            const cleanSrc = playSrc; // p3.vimeos.zip tal cual
            const hls = new Hls({
              enableWorker: true,
              lowLatencyMode: false,
              // ── Buffer VOD ──────────────────────────────────────────────────────
              // Aumentamos el objetivo de buffer para adelantar más segmentos antes
              // de que el usuario los necesite, eliminando micro-pausas en red lenta.
              maxBufferLength: 90,          // segundos de video adelantados (era 60)
              maxMaxBufferLength: 180,       // techo absoluto (era 120)
              maxBufferSize: 120 * 1000 * 1000, // 120 MB en RAM (era 60 MB)
              maxBufferHole: 0.3,           // agujero tolerable antes de nudge (era 0.5)
              highBufferWatchdogPeriod: 3,  // chequeo watchdog (s)
              nudgeMaxRetry: 8,
              // ── Carga de fragmentos ─────────────────────────────────────────────
              // Descarga 3 fragmentos en paralelo para aprovechar el ancho de banda
              // disponible y reducir el tiempo de relleno del buffer.
              maxFragLookUpTolerance: 0.5,
              fragLoadingTimeOut: 20000,
              fragLoadingMaxRetry: 8,
              fragLoadingRetryDelay: 500,   // reintentos más rápidos (era 1000ms)
              fragLoadingMaxRetryTimeout: 8000,
              // ── Manifiestos ─────────────────────────────────────────────────────
              manifestLoadingTimeOut: 20000,
              manifestLoadingMaxRetry: 4,
              levelLoadingTimeOut: 20000,
              levelLoadingMaxRetry: 4,
              // ── ABR / Calidad ───────────────────────────────────────────────────
              // Arrancar siempre en la calidad más alta disponible (vimeos solo
              // ofrece una variante de resolución fija, así que no hay salto de nivel).
              startLevel: -1,               // auto-detect ABR
              abrEwmaFastLive: 3.0,
              abrEwmaSlowLive: 9.0,
              abrEwmaFastVoD: 5.0,
              abrEwmaSlowVoD: 15.0,
              startFragPrefetch: true,
              testBandwidth: true,
              progressive: true,
              fetchSetup: (context, initParams) => {
                const init = initParams || {};
                try {
                  return new Request(context.url, {
                    ...init,
                    method: init.method || 'GET',
                    headers: init.headers,
                    referrer: 'https://vimeos.net/',
                    referrerPolicy: 'no-referrer'
                  });
                } catch {
                  return new Request(context.url, {
                    ...init,
                    referrerPolicy: 'no-referrer'
                  });
                }
              },
              xhrSetup: xhr => {
                try {
                  xhr.withCredentials = false;
                } catch {
                  /* ignore */
                }
              }
            });
            hlsRef.current = hls;
            hls.loadSource(cleanSrc);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, () => {
              if (cancelled) return;
              setReady(true);
              setBuffering(false);
              recoverTriesRef.current = 0;
              const byLabel = new Map();
              (hls.levels || []).forEach((level, index) => {
                const label = level.height ? `${level.height}p` : `${Math.round((level.bitrate || 0) / 1000)}k`;
                const prev = byLabel.get(label);
                if (!prev || (level.bitrate || 0) > (prev.bitrate || 0)) byLabel.set(label, { label, level: index, bitrate: level.bitrate });
              });
              const found = Array.from(byLabel.values())
                .sort((a, b) => parseInt(b.label.replace(/\D/g, ''), 10) - parseInt(a.label.replace(/\D/g, ''), 10))
                .map(({ label, level }) => ({ label, level }));
              setLevels(found);
              // Restaurar posición tras re-load (pausa larga / recover)
              const pos = resumePosRef.current;
              if (pos > 1) {
                try {
                  video.currentTime = pos;
                } catch {
                  /* ignore */
                }
                resumePosRef.current = 0;
              }
              if (autoPlay || userStartedRef.current) video.play().catch(() => {});
            });
            hls.on(Hls.Events.LEVEL_LOADED, (_, data) => {
              if (data?.details && !data.details.live) setReady(true);
            });
            hls.on(Hls.Events.FRAG_BUFFERED, () => {
              if (!cancelled) setBuffering(false);
            });
            hls.on(Hls.Events.ERROR, (_, data) => {
              if (cancelled || !data) return;
              if (!data.fatal) {
                // agujeros / buffer stall: hls.js ya reintenta
                if (data.details === 'bufferStalledError') setBuffering(true);
                // Reintento proactivo en errores de fragmento no-fatales
                if (data.type === Hls.ErrorTypes.NETWORK_ERROR && data.details !== 'manifestLoadError') {
                  try { hls.startLoad(); } catch(_) {}
                }
                return;
              }
              console.warn('[hls] fatal', data.type, data.details, 'try', recoverTriesRef.current);
              setBuffering(true);
              // 1) recuperación in-place con back-off exponencial
              if (recoverTriesRef.current < 4) {
                recoverTriesRef.current += 1;
                const delay = Math.min(500 * recoverTriesRef.current, 2000);
                setTimeout(() => {
                  if (cancelled) return;
                  try {
                    resumePosRef.current = video.currentTime || resumePosRef.current || 0;
                    if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
                      hls.startLoad();
                      return;
                    }
                    if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
                      hls.recoverMediaError();
                      return;
                    }
                  } catch (err) {
                    console.warn('[hls] recover fail', err);
                  }
                  // Si recover tampoco funciona, saltar al siguiente candidato
                  destroyHls();
                  advance(list);
                  tryLoad();
                }, delay);
                return;
              }
              // 2) siguiente candidato de stream
              destroyHls();
              advance(list);
              tryLoad();
            });
            return;
          }

          // Safari nativo
          if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = playSrc;
            setReady(true);
            if (autoPlay || userStartedRef.current) video.play().catch(() => {});
            return;
          }
        } catch (err) {
          console.warn('[hls] load', err);
        }
        advance(list);
        if (!cancelled) tryLoad();
        return;
      }

      // MP4
      video.src = playSrc;
      setReady(true);
      if (autoPlay || userStartedRef.current) video.play().catch(() => {});
    };

    tryLoad();

    return () => {
      cancelled = true;
      destroyHls();
    };
  }, [key, loading, autoPlay, emptyText, pickSrc, advance, streams, t]);

  // Media events
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const onTime = () => {
      if (!dragRef.current) setCurrent(video.currentTime || 0);
    };
    const onMeta = () => setDuration(video.duration || 0);
    const onPlay = () => {
      setPlaying(true);
      setBuffering(false);
      // Si estuvo pausado > 3 min, forzar reload del HLS (tokens CDN caducan)
      const pausedFor = pauseAtRef.current ? (Date.now() - pauseAtRef.current) / 1000 : 0;
      pauseAtRef.current = 0;
      if (pausedFor > 180 && hlsRef.current) {
        try {
          resumePosRef.current = video.currentTime || 0;
          recoverTriesRef.current = 0;
          setBuffering(true);
          hlsRef.current.startLoad();
        } catch (err) {
          console.warn('[hls] resume reload', err);
        }
      }
    };
    const onPause = () => {
      setPlaying(false);
      pauseAtRef.current = Date.now();
    };
    const onEnded = () => {
      setPlaying(false);
      setUi(true);
      setBuffering(false);
    };
    const onVol = () => {
      setMuted(video.muted);
      setVolume(video.volume);
    };
    const onWaiting = () => { bufferingRef.current = true;  setBuffering(true); };
    const onPlaying = () => {
      bufferingRef.current = false;
      setBuffering(false);
      setPlaying(true);
    };
    const onCanPlay = () => { bufferingRef.current = false; setBuffering(false); };
    const onCanPlayThrough = () => { bufferingRef.current = false; setBuffering(false); };
    const onSeeking = () => { bufferingRef.current = true;  setBuffering(true); };
    const onSeeked = () => {
      // tras seek agresivo, si el buffer está vacío hls rellenará
      if (video.readyState >= 3) { bufferingRef.current = false; setBuffering(false); }
    };
    const onProgress = () => {
      // `progress` indica que el browser acaba de recibir datos: si estábamos
      // en buffering y ya hay suficiente datos (readyState HAVE_FUTURE_DATA)
      // quitamos el spinner sin esperar al evento `playing`.
      // Leemos bufferingRef.current (no el state) para evitar closure stale.
      if (bufferingRef.current && video.readyState >= 3) {
        bufferingRef.current = false;
        setBuffering(false);
      }
    };
    const onErr = () => {
      console.warn('[video] element error', video.error);
      setBuffering(false);
    };
    video.addEventListener('timeupdate', onTime);
    video.addEventListener('loadedmetadata', onMeta);
    video.addEventListener('durationchange', onMeta);
    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);
    video.addEventListener('ended', onEnded);
    video.addEventListener('volumechange', onVol);
    video.addEventListener('waiting', onWaiting);
    video.addEventListener('playing', onPlaying);
    video.addEventListener('canplay', onCanPlay);
    video.addEventListener('canplaythrough', onCanPlayThrough);
    video.addEventListener('progress', onProgress);
    video.addEventListener('seeking', onSeeking);
    video.addEventListener('seeked', onSeeked);
    video.addEventListener('error', onErr);
    return () => {
      video.removeEventListener('timeupdate', onTime);
      video.removeEventListener('loadedmetadata', onMeta);
      video.removeEventListener('durationchange', onMeta);
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
      video.removeEventListener('ended', onEnded);
      video.removeEventListener('volumechange', onVol);
      video.removeEventListener('waiting', onWaiting);
      video.removeEventListener('playing', onPlaying);
      video.removeEventListener('canplay', onCanPlay);
      video.removeEventListener('canplaythrough', onCanPlayThrough);
      video.removeEventListener('progress', onProgress);
      video.removeEventListener('seeking', onSeeking);
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', onErr);
    };
  }, []);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.volume = volume;
    v.muted = muted;
  }, [volume, muted]);

  // ── Visibilidad de controles ──────────────────────────────────────────
  // El temporizador anterior se creaba con un `playing` viejo (antes de dar
  // play), así que en pantalla completa nunca se ocultaban. Ahora el cierre
  // depende del estado real y se reinicia con cada movimiento.
  const clearHide = useCallback(() => {
    window.clearTimeout(hideTimer.current);
    hideTimer.current = 0;
  }, []);

  const armHide = useCallback(
    (delay = 3200) => {
      clearHide();
      if (!playingRef.current) return;
      if (subOpen || qualityOpen || langOpen) return;
      hideTimer.current = window.setTimeout(() => setUi(false), delay);
    },
    [clearHide, subOpen, qualityOpen]
  );

  const showUi = useCallback(() => {
    setUi(true);
    armHide();
  }, [armHide]);

  useEffect(() => {
    if (!playing || subOpen || qualityOpen || langOpen || adPhase === 'ad') {
      clearHide();
      setUi(true);
      return undefined;
    }
    armHide();
    return clearHide;
  }, [playing, subOpen, qualityOpen, langOpen, adPhase, armHide, clearHide]);

  useEffect(() => () => {
    clearHide();
    window.clearTimeout(singleTapRef.current);
    window.clearTimeout(flashTimerRef.current);
  }, [clearHide]);

  const toggle = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => {});
    else v.pause();
  }, []);

  const seekBy = useCallback(
    delta => {
      const v = videoRef.current;
      if (!v) return;
    const max = Number.isFinite(v.duration) ? v.duration : Infinity;
    v.currentTime = Math.min(max, Math.max(0, (v.currentTime || 0) + delta));
    setCurrent(v.currentTime);
    // Sin aviso central: el salto debe sentirse en el vídeo, no taparlo.
  },
  []
);

  const nudgeVolume = useCallback(delta => {
    const v = videoRef.current;
    if (!v) return;
    const next = Math.min(1, Math.max(0, (v.muted ? 0 : v.volume) + delta));
    setVolume(next);
    setMuted(next === 0);
    setFlash({ volume: next, id: Date.now() });
    window.clearTimeout(flashTimerRef.current);
    flashTimerRef.current = window.setTimeout(() => setFlash(null), 720);
  }, []);

  const onBarDown = e => {
    const bar = barRef.current;
    const v = videoRef.current;
    if (!bar || !v || !duration) return;
    dragRef.current = true;
    bar.setPointerCapture?.(e.pointerId);
    const rect = bar.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    v.currentTime = ratio * duration;
    setCurrent(v.currentTime);
  };

  const onBarMove = e => {
    if (!dragRef.current) return;
    const bar = barRef.current;
    const v = videoRef.current;
    if (!bar || !v || !duration) return;
    const rect = bar.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    v.currentTime = ratio * duration;
    setCurrent(v.currentTime);
  };

  const onBarUp = e => {
    dragRef.current = false;
    barRef.current?.releasePointerCapture?.(e.pointerId);
  };

  const toggleFull = async () => {
    const root = rootRef.current;
    const video = videoRef.current;
    if (!root) return;
    try {
      if (document.fullscreenElement || document.webkitFullscreenElement) {
        await (document.exitFullscreen?.() || document.webkitExitFullscreen?.());
        setFull(false);
      } else if (root.requestFullscreen) {
        await root.requestFullscreen();
        setFull(true);
      } else if (video?.webkitEnterFullscreen) {
        video.webkitEnterFullscreen();
        setFull(true);
      }
    } catch {
      /* el navegador puede bloquear la petición */
    }
  };

  useEffect(() => {
    const onFs = () => setFull(Boolean(document.fullscreenElement || document.webkitFullscreenElement));
    document.addEventListener('fullscreenchange', onFs);
    document.addEventListener('webkitfullscreenchange', onFs);
    return () => {
      document.removeEventListener('fullscreenchange', onFs);
      document.removeEventListener('webkitfullscreenchange', onFs);
    };
  }, []);

  const applyQuality = level => {
    const hls = hlsRef.current;
    if (hls) hls.currentLevel = level;
    setQuality(level);
    setQualityOpen(false);
    setSubOpen(false);
    showUi();
  };

  // ── Teclado (solo con el reproductor activo o a pantalla completa) ──
  useEffect(() => {
    const onKey = event => {
      if (event.defaultPrevented || isTyping(event.target)) return;
      const root = rootRef.current;
      const inside = root && (root.contains(document.activeElement) || hoveringRef.current);
      if (!inside && !document.fullscreenElement) return;
      const video = videoRef.current;
      if (!video) return;
      const key = event.key.toLowerCase();

      if (key === ' ' || key === 'k') {
        event.preventDefault();
        toggle();
        showUi();
      } else if (key === 'j') {
        event.preventDefault();
        seekBy(-5);
        showUi();
      } else if (key === 'l') {
        event.preventDefault();
        seekBy(5);
        showUi();
      } else if (key === 'arrowleft') {
        event.preventDefault();
        seekBy(-5);
        showUi();
      } else if (key === 'arrowright') {
        event.preventDefault();
        seekBy(5);
        showUi();
      } else if (key === 'arrowup') {
        event.preventDefault();
        nudgeVolume(0.05);
        showUi();
      } else if (key === 'arrowdown') {
        event.preventDefault();
        nudgeVolume(-0.05);
        showUi();
      } else if (key === 'm') {
        event.preventDefault();
        setMuted(value => !value);
        showUi();
      } else if (key === 'f') {
        event.preventDefault();
        toggleFull();
      } else if (key === 'c' && canSubs) {
        event.preventDefault();
        setSubOpen(value => !value);
        setQualityOpen(false);
        showUi();
      } else if (key === 'escape') {
        setSubOpen(false);
        setQualityOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [canSubs, nudgeVolume, seekBy, showUi, toggle]);

  // Toques en el vídeo:
  //  · primero, con los controles ocultos → los muestra (no pausa).
  //  · siguiente, ya visibles → reproduce/pausa.
  //  · doble toque (< 330 ms) → ±10 s, sin revelar los controles.
  // En escritorio el hover ya los muestra, así que el clic pausa como siempre.
  const onSurfaceClick = event => {
    if (event.target.closest('button, input, a, .stream-player__subs-menu, .stream-player__quality-menu')) return;
    if (showGate) {
      startPlayback();
      return;
    }
    const now = performance.now();
    const last = tapRef.current;
    const isDouble = now - last.time < 330 && Math.abs(event.clientX - last.x) < 80;

    if (isDouble) {
      window.clearTimeout(singleTapRef.current);
      tapRef.current = { time: 0, x: 0 };
      const rect = event.currentTarget.getBoundingClientRect();
      const ratio = (event.clientX - rect.left) / rect.width;
      if (duration) {
        seekBy(ratio < 0.5 ? -10 : 10);
        setUi(false);
        clearHide();
      }
      return;
    }

    tapRef.current = { time: now, x: event.clientX };
    window.clearTimeout(singleTapRef.current);
    const wasVisible = surfaceVisibleRef.current;
    singleTapRef.current = window.setTimeout(() => {
      if (wasVisible) toggle();
      else {
        setUi(true);
        armHide();
      }
    }, 220);
  };

  const onSurfaceDown = event => {
    if (event.target.closest('button, input, a')) return;
    const now = performance.now();
    if (now - tapRef.current.time < 330) {
      // Segundo toque del doble toque: el clic decide (saltar y ocultar).
      return;
    }
    // Se guarda cómo estaban los controles ANTES de este toque. Si estaban
    // ocultos no se muestran aún: así el primer toque de un doble toque no
    // hace parpadear los botones. El clic los revela 220 ms después.
    surfaceVisibleRef.current = uiRef.current;
    if (surfaceVisibleRef.current) showUi();
  };

  const clearSubTrack = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      Array.from(video.querySelectorAll('track[data-kinora]')).forEach(el => el.remove());
      Array.from(video.textTracks || []).forEach(tr => {
        try {
          tr.mode = 'disabled';
        } catch {
          /* */
        }
      });
    }
    if (subUrlRef.current) {
      URL.revokeObjectURL(subUrlRef.current);
      subUrlRef.current = null;
    }
  }, []);

  const loadSubList = useCallback(async () => {
    if (!canSubs) return;
    setSubLoading(true);
    setSubError('');
    try {
      const q = new URLSearchParams();
      if (tmdbId) q.set('id', String(tmdbId));
      if (imdbId) q.set('imdb', String(imdbId));
      q.set('media', mediaType === 'tv' ? 'tv' : 'movie');
      if (mediaType === 'tv') {
        if (season != null) q.set('season', String(season));
        if (episode != null) q.set('episode', String(episode));
      }
      // Preferir ES latino / ES / EN / PT
      q.set('lang', 'es,es-MX,es-ES,en,pt-BR,pt-PT,fr,it,de,ja,ko');
      const r = await fetch(`/api/subs?${q}`);
      const data = await r.json();
      if (!data?.ok) {
        setSubError(data?.error || t('player.searchSubsError'));
        setSubList([]);
      } else {
        setSubList(data.subs || []);
        if (!(data.subs || []).length) setSubError(t('player.noSubs'));
      }
    } catch (err) {
      setSubError(err?.message || t('player.searchSubsError'));
      setSubList([]);
    } finally {
      setSubLoading(false);
    }
  }, [canSubs, tmdbId, imdbId, mediaType, season, episode, t]);

  const attachVtt = useCallback(
    (text, sub) => {
      const video = videoRef.current;
      if (!video) return;
      clearSubTrack();
      const blob = new Blob([text], { type: 'text/vtt' });
      const url = URL.createObjectURL(blob);
      subUrlRef.current = url;
      const track = document.createElement('track');
      track.kind = 'subtitles';
      track.label = sub.label || sub.language || 'Subs';
      track.srclang = (sub.language || 'es').slice(0, 8);
      track.src = url;
      track.default = true;
      track.setAttribute('data-kinora', '1');
      video.appendChild(track);
      const enable = () => {
        const tracks = video.textTracks;
        for (let i = 0; i < tracks.length; i++) {
          tracks[i].mode = i === tracks.length - 1 ? 'showing' : 'disabled';
        }
      };
      track.addEventListener('load', enable);
      setTimeout(enable, 200);
      setActiveSub(sub);
      setSubOpen(false);
    },
    [clearSubTrack]
  );

  const applySub = useCallback(
    async sub => {
      const video = videoRef.current;
      if (!video || !sub?.file_id) return;
      setSubLoading(true);
      setSubError('');
      try {
        const cached = getCachedSub(sub.file_id);
        if (cached?.vtt) {
          attachVtt(cached.vtt, sub);
          return;
        }
        const r = await fetch(`/api/subs/download?file_id=${sub.file_id}`);
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.error || `HTTP ${r.status}`);
        }
        const text = await r.text();
        setCachedSub(sub.file_id, {
          vtt: text,
          label: sub.label,
          language: sub.language
        });
        attachVtt(text, sub);
      } catch (err) {
        setSubError(err?.message || t('player.searchSubsError'));
      } finally {
        setSubLoading(false);
      }
    },
    [attachVtt, t]
  );

  const disableSubs = useCallback(() => {
    clearSubTrack();
    setActiveSub(null);
    setSubOpen(false);
  }, [clearSubTrack]);

  // Al cambiar de título / episodio, limpiar pista y estado de play/ad.
  // NO depende de `key` (URLs del stream): si no, al resolver el HLS se resetea
  // userStarted y desaparecen la barra y los controles.
  useEffect(() => {
    clearSubTrack();
    setActiveSub(null);
    setSubList([]);
    setSubError('');
    setSubOpen(false);
    setQualityOpen(false);
    setUserStarted(false);
    userStartedRef.current = false;
    setAdPhase(null);
    setAdLeft(5);
    window.clearInterval(adTimerRef.current);
  }, [tmdbId, imdbId, mediaType, season, episode, clearSubTrack]);

  useEffect(() => {
    if (subOpen && !subList.length && !subLoading) loadSubList();
  }, [subOpen, subList.length, subLoading, loadSubList]);

  useEffect(() => {
    if (!subOpen && !qualityOpen && !langOpen) return undefined;
    const onDown = event => {
      if (!rootRef.current?.contains(event.target)) {
        setSubOpen(false);
        setQualityOpen(false);
      }
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [subOpen, qualityOpen, langOpen]);

  const pct = duration > 0 ? (current / duration) * 100 : 0;
  const showEmpty = !loading && !streams?.length && Boolean(failed || !streams);
  const showError = Boolean(failed) || (showEmpty && !loading);
  const showGate = !userStarted && !showError && adPhase !== 'ad';
  const showAd = adPhase === 'ad' && !userStarted && !showError;
  const streamReady = Boolean(streams?.length) && !loading;
  const volumePct = muted ? 0 : Math.round(volume * 100);
  const qualityLabel = quality < 0 ? t('player.auto') : levels.find(entry => entry.level === quality)?.label || t('player.auto');

  const finishAdAndPlay = () => {
    window.clearInterval(adTimerRef.current);
    if (adVideoRef.current) {
      try {
        adVideoRef.current.pause();
      } catch {
        /* el nodo puede estar ya desmontado */
      }
    }
    setAdPhase(null);
    userStartedRef.current = true;
    setUserStarted(true);
    const tryPlay = () => {
      const v = videoRef.current;
      if (v) v.play().catch(() => {});
    };
    tryPlay();
    // si el stream aún no listo, el effect de hls/mp4 usará userStartedRef
    if (!streamReady) {
      const id = window.setInterval(() => {
        if (streams?.length && videoRef.current) {
          tryPlay();
          window.clearInterval(id);
        }
      }, 400);
      window.setTimeout(() => window.clearInterval(id), 30000);
    }
  };

  const startPlayback = () => {
    // Siempre se puede pulsar: anuncio 5s (saltar al final)
    if (userStarted || adPhase === 'ad') return;
    setAdPhase('ad');
    setAdLeft(5);
    window.clearInterval(adTimerRef.current);
    adTimerRef.current = window.setInterval(() => {
      setAdLeft(n => {
        if (n <= 1) {
          window.clearInterval(adTimerRef.current);
          return 0;
        }
        return n - 1;
      });
    }, 1000);
  };

  useEffect(() => () => window.clearInterval(adTimerRef.current), []);

  // Preroll: se pide el VAST mientras corre la cuenta de 5 s. Con
  // consentimiento de publicidad (Política §8); sin él queda el marcador.
  useEffect(() => {
    if (adPhase !== 'ad') return undefined;
    if (!canShowPersonalizedAds()) {
      setAdStatus('empty');
      return undefined;
    }

    const controller = new AbortController();
    let alive = true;
    setAdStatus('loading');

    loadVastPreroll({ signal: controller.signal, viewportWidth: window.innerWidth })
      .then(ad => {
        if (!alive) return;
        setPreroll(ad);
        setAdStatus('ready');
        fireAdPixel(ad.impression);
      })
      .catch(error => {
        if (!alive || error?.name === 'AbortError') return;
        console.info('[ads] preroll sin relleno:', error?.message || error);
        setPreroll(null);
        setAdStatus('empty');
      });

    return () => {
      alive = false;
      controller.abort();
    };
  }, [adPhase]);

  // El clic que abrió el anuncio cuenta como gesto: se intenta con sonido y,
  // si el navegador lo bloquea, se cae a silenciado antes de darlo por perdido.
  useEffect(() => {
    if (!preroll?.mediaUrl) return undefined;
    const video = adVideoRef.current;
    if (!video) return undefined;
    const attempt = video.play();
    attempt?.catch?.(() => {
      video.muted = true;
      video.play().catch(() => {});
    });
    return undefined;
  }, [preroll?.mediaUrl]);

  const surfaceHandlers = {
    onPointerDown: onSurfaceDown,
    onPointerMove: () => {
      hoveringRef.current = true;
      showUi();
    },
    onPointerLeave: () => {
      hoveringRef.current = false;
    },
    onClick: onSurfaceClick
  };

  return (
    <div
      ref={rootRef}
      className={`stream-player ${ui || !playing || showGate || showAd ? 'stream-player--ui' : ''}${full ? ' is-full' : ''}`}
      onPointerEnter={() => {
        hoveringRef.current = true;
      }}
      onPointerMove={() => {
        hoveringRef.current = true;
        showUi();
      }}
      onPointerLeave={() => {
        hoveringRef.current = false;
      }}
      tabIndex={-1}
    >
      <video ref={videoRef} className="stream-player__video" playsInline preload="auto" poster={poster || undefined} {...surfaceHandlers} />

      {showError ? (
        <div className="stream-player__msg" role="status">
          <p>{failed || emptyText || t('player.unavailable')}</p>
        </div>
      ) : null}

      {showGate ? (
        <div className="stream-player__gate">
          {poster ? (
            <div className="stream-player__gate-bg" style={{ backgroundImage: `url(${poster})` }} aria-hidden />
          ) : null}
          <div className="stream-player__gate-veil" aria-hidden />
          <button type="button" className="stream-player__gate-play" aria-label={t('player.play')} onClick={startPlayback}>
            <img src="/assets/kinora-logo.svg" alt="" width={96} height={96} draggable={false} />
          </button>
          <p className="stream-player__verse">
            <span className="stream-player__verse-text">“{verse.text}”</span>
            <span className="stream-player__verse-ref">— {verse.ref}</span>
          </p>
          {!streamReady ? <p className="stream-player__gate-hint">{t('player.preparing')}</p> : null}
        </div>
      ) : null}

      {showAd ? (
        <div className="stream-player__ad" role="dialog" aria-label={t('player.ad')}>
          <div className="stream-player__ad-card">
            <p className="stream-player__ad-label">{t('player.ad')}</p>
            {/* Preroll VAST (HilltopAds): se reproduce dentro del player y la
                cuenta de 5 s es la que habilita el botón de saltar. */}
            <div className="stream-player__ad-slot" id="kinora-preroll-ad">
              {preroll?.mediaUrl ? (
                <a
                  className="stream-player__ad-media"
                  href={preroll.clickThrough || undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={t('player.ad')}
                  onClick={event => {
                    if (!preroll.clickThrough) event.preventDefault();
                  }}
                >
                  <video
                    ref={adVideoRef}
                    className="stream-player__ad-video"
                    src={preroll.mediaUrl}
                    autoPlay
                    playsInline
                    preload="auto"
                    onEnded={finishAdAndPlay}
                  />
                </a>
              ) : adStatus === 'loading' ? (
                <span className="stream-player__ad-spinner" aria-hidden />
              ) : (
                <p className="stream-player__ad-placeholder">
                  <span>{t('player.adUnavailable')}</span>
                  <small>{t('player.adSpace')}</small>
                </p>
              )}
            </div>
            <button
              type="button"
              className="stream-player__ad-skip"
              disabled={adLeft > 0}
              onClick={finishAdAndPlay}
            >
              {adLeft > 0 ? t('player.skipIn', { n: adLeft }) : t('player.skipAd')}
            </button>
          </div>
        </div>
      ) : null}

      {/* Loader: arranque o buffering durante reproducción */}
      {!showGate && !showAd && !showError && (buffering || (!ready && streams?.length)) ? (
        <div className="stream-player__boot" aria-hidden>
          <span className="stream-player__spinner" />
        </div>
      ) : null}

      {/* Play / pausa grande al centro (después del gate / anuncio) */}
      {!showGate && !showAd && !showError && ready && !buffering ? (
        <button
          type="button"
          className={`stream-player__center-btn${playing ? ' is-playing' : ''}`}
          aria-label={playing ? t('player.pause') : t('player.play')}
          onClick={e => {
            e.stopPropagation();
            toggle();
          }}
        >
          {playing ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          ) : (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M8 5v14l11-7L8 5z" />
            </svg>
          )}
        </button>
      ) : null}

      {!showGate && !showAd && !showError ? (
        <div className="stream-player__ctl">
          <div
            className="stream-player__track"
            ref={barRef}
            onPointerDown={onBarDown}
            onPointerMove={onBarMove}
            onPointerUp={onBarUp}
            role="slider"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(pct)}
            aria-label={t('player.playing')}
          >
            <span className="stream-player__played" style={{ width: `${pct}%` }} />
            <span className="stream-player__knob" style={{ left: `${pct}%` }} />
          </div>
          <div className="stream-player__row">
            <button type="button" className="stream-player__btn" aria-label={playing ? t('player.pause') : t('player.play')} onClick={toggle}>
              {playing ? <Pause size={18} fill="currentColor" strokeWidth={0} /> : <Play size={18} fill="currentColor" strokeWidth={0} />}
            </button>
            <button
              type="button"
              className="stream-player__btn stream-player__seek"
              aria-label={t('player.seekBack')}
              title={t('player.seekBack')}
              onClick={() => {
                seekBy(-5);
                showUi();
              }}
            >
              <RotateCcw size={18} />
              <span className="stream-player__seek-num">5</span>
            </button>
            <button
              type="button"
              className="stream-player__btn stream-player__seek"
              aria-label={t('player.seekForward')}
              title={t('player.seekForward')}
              onClick={() => {
                seekBy(5);
                showUi();
              }}
            >
              <RotateCw size={18} />
              <span className="stream-player__seek-num">5</span>
            </button>
            <span className="stream-player__time">
              {fmt(current)} / {fmt(duration)}
            </span>
            <span className="stream-player__spacer" />

            <div className="stream-player__vol">
              <button
                type="button"
                className="stream-player__btn"
                aria-label={muted ? t('player.unmute') : t('player.mute')}
                onClick={() => setMuted(m => !m)}
              >
                {muted || volume === 0 ? <VolumeX size={17} /> : <Volume2 size={17} />}
              </button>
              <input
                className="stream-player__range"
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={muted ? 0 : volume}
                style={{ '--sp-vol': `${volumePct}%` }}
                onChange={e => {
                  const v = Number(e.target.value);
                  setVolume(v);
                  setMuted(v === 0);
                }}
                aria-label={t('player.volume')}
              />
            </div>


            <div className="stream-player__pop">
              <button
                type="button"
                className={`stream-player__btn ${audioLang ? 'is-on' : ''}`}
                aria-label={t('player.langAudio')}
                title={t('player.langAudio')}
                aria-expanded={langOpen}
                onClick={() => {
                  setLangOpen(o => !o);
                  setSubOpen(false);
                  setQualityOpen(false);
                }}
              >
                <Languages size={17} />
              </button>
              {langOpen ? (
                <div className="stream-player__menu stream-player__lang-menu" role="menu">
                  <p className="stream-player__menu-label">{t('player.langAudio')}</p>
                  {((availableLangs && availableLangs.length) ? availableLangs : DEFAULT_AUDIO_LANGS).map(row => {
                    const code = row.code || row;
                    let label = row.label_es || row.label_en || '';
                    if (!label && row.labelKey) {
                      try { label = t(row.labelKey); } catch { label = ''; }
                    }
                    if (!label) {
                      const map = {
                        'es-MX': 'player.langEsMx',
                        'es-ES': 'player.langEsEs',
                        en: 'player.langEn',
                        fr: 'player.langFr',
                        'pt-BR': 'player.langPtBr',
                      };
                      label = map[code] ? t(map[code]) : String(code);
                    }
                    return (
                      <button
                        key={code}
                        type="button"
                        className={`stream-player__menu-item ${audioLang === code ? 'is-active' : ''}`}
                        onClick={() => {
                          setLangOpen(false);
                          if (code !== audioLang && onAudioLangChange) onAudioLangChange(code);
                        }}
                      >
                        <span>{label}</span>
                        {audioLang === code ? <Check size={13} /> : null}
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>

            {canSubs ? (
              <div className="stream-player__pop">
                <button
                  type="button"
                  className={`stream-player__btn ${activeSub ? 'is-on' : ''}`}
                  aria-label={t('player.subtitles')}
                  title={t('player.subtitles')}
                  aria-expanded={subOpen}
                  onClick={() => {
                    setSubOpen(o => !o);
                    setQualityOpen(false);
                    setLangOpen(false);
                  }}
                >
                  <Captions size={17} />
                </button>
                {subOpen ? (
                  <div className="stream-player__menu stream-player__subs-menu" role="menu">
                    <p className="stream-player__menu-label">{t('player.subtitles')}</p>
                    <button
                      type="button"
                      className={`stream-player__menu-item ${!activeSub ? 'is-active' : ''}`}
                      onClick={disableSubs}
                    >
                      <span>{t('player.disable')}</span>
                      {!activeSub ? <Check size={13} /> : null}
                    </button>
                    {subLoading ? <p className="stream-player__menu-hint">{t('player.searchSubs')}</p> : null}
                    {subError && !subList.length ? <p className="stream-player__menu-hint">{subError}</p> : null}
                    {subList.map(s => (
                      <button
                        key={`${s.file_id}-${s.language}`}
                        type="button"
                        className={`stream-player__menu-item ${activeSub?.file_id === s.file_id ? 'is-active' : ''}`}
                        onClick={() => applySub(s)}
                      >
                        <span>{s.label || s.language}</span>
                        <small>
                          {s.hearing_impaired ? 'SDH · ' : ''}
                          {s.ai_translated || s.machine_translated ? 'IA · ' : ''}
                          {(s.downloads || 0) > 0 ? s.downloads : ''}
                        </small>
                      </button>
                    ))}
                    {!subLoading && subList.length ? (
                      <button type="button" className="stream-player__menu-item is-accent" onClick={loadSubList}>
                        {t('player.refresh')}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="stream-player__pop">
              <button
                type="button"
                className={`stream-player__btn stream-player__quality-btn ${quality >= 0 ? 'is-on' : ''}`}
                aria-label={t('player.quality')}
                title={t('player.quality')}
                aria-expanded={qualityOpen}
                onClick={() => {
                  setQualityOpen(o => !o);
                  setSubOpen(false);
                  setLangOpen(false);
                }}
              >
                <Settings2 size={17} />
                <span className="stream-player__quality-tag">{qualityLabel}</span>
              </button>
              {qualityOpen ? (
                <div className="stream-player__menu stream-player__quality-menu" role="menu">
                  <p className="stream-player__menu-label">{t('player.quality')}</p>
                  <button
                    type="button"
                    className={`stream-player__menu-item ${quality < 0 ? 'is-active' : ''}`}
                    onClick={() => applyQuality(-1)}
                  >
                    <span>{t('player.auto')}</span>
                    {quality < 0 ? <Check size={13} /> : null}
                  </button>
                  {levels.map(({ label, level }) => (
                    <button
                      key={label}
                      type="button"
                      className={`stream-player__menu-item ${quality === level ? 'is-active' : ''}`}
                      onClick={() => applyQuality(level)}
                    >
                      <span>{label}</span>
                      {quality === level ? <Check size={13} /> : null}
                    </button>
                  ))}
                  {levels.length <= 1 ? <p className="stream-player__menu-hint">{t('player.qualityUnavailable')}</p> : null}
                </div>
              ) : null}
            </div>

            <button type="button" className="stream-player__btn" aria-label={full ? t('player.exitFullscreen') : t('player.fullscreen')} onClick={toggleFull}>
              {full ? <Minimize size={17} /> : <Maximize size={17} />}
            </button>
          </div>
        </div>
      ) : null}

      {flash ? (
        <div className="stream-player__flash stream-player__flash--vol" aria-hidden>
          {flash.volume === 0 ? <VolumeX size={20} /> : <Volume2 size={20} />}
          <span>{Math.round(flash.volume * 100)}%</span>
        </div>
      ) : null}
    </div>
  );
}