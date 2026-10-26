'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Maximize, Minimize, Pause, Play, RotateCcw, RotateCw, Volume2, VolumeX } from 'lucide-react';
import './Player.css';

let ytPromise = null;

// Carga la IFrame API una sola vez por pagina.
const loadYouTube = () => {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (ytPromise) return ytPromise;
  ytPromise = new Promise((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      resolve(window.YT);
    };
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    tag.async = true;
    tag.onerror = () => reject(new Error('No se pudo cargar YouTube.'));
    document.head.appendChild(tag);
    window.setTimeout(() => {
      if (window.YT?.Player) resolve(window.YT);
      else reject(new Error('YouTube tardo demasiado en responder.'));
    }, 12000);
  });
  return ytPromise;
};

const fmt = s => {
  if (!Number.isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
};

export default function Player({
  videoId,
  poster,
  badge = '',
  autoPlay = false,
  emptyText = 'Aun no hay video disponible para este titulo.'
}) {
  const hostRef = useRef(null);
  const frameRef = useRef(null);
  const barRef = useRef(null);
  const playerRef = useRef(null);
  const hideTimer = useRef(0);
  const dragRef = useRef(false);
  const durationRef = useRef(0);
  const resumeRef = useRef(false);
  const volRef = useRef({ volume: 80, muted: false });

  const [failed, setFailed] = useState('');
  const [playing, setPlaying] = useState(false);
  const [started, setStarted] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(80);
  const [full, setFull] = useState(false);
  const [uiVisible, setUiVisible] = useState(true);
  const [seeking, setSeeking] = useState(null);

  // Mantiene volumen/silencio y la reproduccion al recrear el jugador (cambio de episodio).
  volRef.current = { volume, muted };

  // El jugador se recrea al cambiar de video (p. ej. al cambiar de episodio).
  useEffect(() => {
    let dead = false;
    setFailed('');
    setPlaying(false);
    setStarted(false);
    setCurrent(0);
    setDuration(0);
    durationRef.current = 0;
    if (!videoId) return undefined;

    loadYouTube()
      .then(YT => {
        if (dead || !hostRef.current) return;
        const mount = document.createElement('div');
        hostRef.current.replaceChildren(mount);
        playerRef.current = new YT.Player(mount, {
          videoId,
          playerVars: {
            controls: 0,
            disablekb: 1,
            modestbranding: 1,
            rel: 0,
            playsinline: 1,
            fs: 0,
            origin: window.location.origin
          },
          events: {
            onReady: e => {
              if (dead) return;
              e.target.setVolume?.(volRef.current.volume);
              if (volRef.current.muted) e.target.mute?.();
              if (resumeRef.current) {
                resumeRef.current = false;
                e.target.playVideo?.();
              } else if (autoPlay) {
                e.target.playVideo?.();
              }
            },
            onStateChange: e => {
              if (dead) return;
              setPlaying(e.data === 1);
              if (e.data === 1) setStarted(true);
              if (e.data === 1 || e.data === 3 || e.data === 0 || e.data === 5) {
                const d = e.target.getDuration?.() || 0;
                durationRef.current = d;
                setDuration(d);
              }
            },
            onError: () => {
              if (!dead) setFailed('Este video no esta disponible.');
            }
          }
        });
      })
      .catch(err => {
        if (!dead) setFailed(err?.message || 'No se pudo cargar el reproductor.');
      });

    return () => {
      dead = true;
      clearTimeout(hideTimer.current);
      try {
        if (playerRef.current?.getPlayerState?.() === 1) resumeRef.current = true;
        playerRef.current?.destroy();
      } catch {}
      playerRef.current = null;
      hostRef.current?.replaceChildren();
    };
  }, [videoId, autoPlay]);

  // Reloj de progreso.
  useEffect(() => {
    if (!videoId || failed) return undefined;
    const id = window.setInterval(() => {
      const p = playerRef.current;
      if (!p?.getCurrentTime) return;
      try {
        setCurrent(p.getCurrentTime() || 0);
        const d = p.getDuration?.() || 0;
        if (d) {
          durationRef.current = d;
          setDuration(d);
        }
      } catch {}
    }, 250);
    return () => window.clearInterval(id);
  }, [videoId, failed]);

  // Los controles se solapan al dejar el cursor quieto mientras reproduce.
  const wake = useCallback(() => {
    setUiVisible(true);
    clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => {
      const state = playerRef.current?.getPlayerState?.();
      setUiVisible(state !== 1);
    }, 2600);
  }, []);

  useEffect(() => () => clearTimeout(hideTimer.current), []);

  useEffect(() => {
    const onFull = () => setFull(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFull);
    return () => document.removeEventListener('fullscreenchange', onFull);
  }, []);

  const toggle = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (p.getPlayerState?.() === 1) p.pauseVideo();
    else p.playVideo();
    wake();
  }, [wake]);

  const skip = useCallback(
    delta => {
      const p = playerRef.current;
      if (!p) return;
      const wasPlaying = p.getPlayerState?.() === 1;
      const d = durationRef.current || p.getDuration?.() || 0;
      const t = Math.max(0, Math.min((p.getCurrentTime?.() || 0) + delta, d || Infinity));
      p.seekTo(t, true);
      // Un salto nunca debe dejar el video en pausa.
      if (wasPlaying) p.playVideo?.();
      setCurrent(t);
      wake();
    },
    [wake]
  );

  const seekRatio = useCallback(ratio => {
    const p = playerRef.current;
    const d = durationRef.current;
    if (!p || !d) return;
    const t = ratio * d;
    p.seekTo(t, true);
    setCurrent(t);
  }, []);

  const toggleMute = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (muted) {
      p.unMute();
      p.setVolume(volume || 60);
      setMuted(false);
    } else {
      p.mute();
      setMuted(true);
    }
    wake();
  }, [muted, volume, wake]);

  const changeVolume = value => {
    setVolume(value);
    const p = playerRef.current;
    if (!p) return;
    p.setVolume(value);
    if (value > 0 && muted) {
      p.unMute();
      setMuted(false);
    }
  };

  const toggleFull = useCallback(() => {
    const el = frameRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else el.requestFullscreen?.();
  }, []);

  const onKey = e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === ' ') {
      e.preventDefault();
      toggle();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      skip(15);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      skip(-15);
    } else if (e.key.toLowerCase() === 'm') toggleMute();
    else if (e.key.toLowerCase() === 'f') toggleFull();
  };

  const ratioFrom = e => {
    const r = barRef.current.getBoundingClientRect();
    return Math.min(1, Math.max(0, (e.clientX - r.left) / Math.max(1, r.width)));
  };

  const onTrackDown = e => {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = true;
    const r = ratioFrom(e);
    setSeeking(r);
    seekRatio(r);
    wake();
  };

  const onTrackMove = e => {
    if (!dragRef.current) return;
    const r = ratioFrom(e);
    setSeeking(r);
    seekRatio(r);
  };

  const onTrackUp = e => {
    if (!dragRef.current) return;
    dragRef.current = false;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}
    setSeeking(null);
    wake();
  };

  const shownTime = seeking !== null ? seeking * duration : current;
  const pct = duration ? Math.min(100, (shownTime / duration) * 100) : 0;
  const showBig = Boolean(videoId) && !failed && !playing;

  return (
    <div
      ref={frameRef}
      className="player"
      data-ui={uiVisible || !playing ? '' : undefined}
      data-full={full ? '' : undefined}
      tabIndex={0}
      onPointerMove={wake}
      onPointerDown={wake}
      onKeyDown={onKey}
      aria-label="Reproductor"
    >
      <div className="player__host" ref={hostRef} />

      {poster && !started ? <img className="player__poster" src={poster} alt="" aria-hidden="true" /> : null}

      {failed || !videoId ? (
        <div className="player__fallback">
          <p>{failed || emptyText}</p>
        </div>
      ) : null}

      {badge ? <span className="player__badge">{badge}</span> : null}

      {showBig ? (
        <button type="button" className="player__big" aria-label="Reproducir" onClick={toggle}>
          <Play size={30} fill="currentColor" strokeWidth={0} />
        </button>
      ) : null}

      <div className="player__ctl">
        <div
          className="player__track"
          ref={barRef}
          onPointerDown={onTrackDown}
          onPointerMove={onTrackMove}
          onPointerUp={onTrackUp}
          role="slider"
          aria-label="Progreso"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pct)}
        >
          <span className="player__played" style={{ width: `${pct}%` }} />
          <span className="player__knob" style={{ left: `${pct}%` }} />
        </div>

        <div className="player__row">
          <button type="button" className="player__btn" aria-label={playing ? 'Pausar' : 'Reproducir'} onClick={toggle}>
            {playing ? <Pause size={18} fill="currentColor" strokeWidth={0} /> : <Play size={18} fill="currentColor" strokeWidth={0} />}
          </button>
          <button type="button" className="player__btn player__skip" aria-label="Retroceder 15 segundos" onClick={() => skip(-15)}>
            <RotateCcw size={17} />
            <i>15</i>
          </button>
          <button type="button" className="player__btn player__skip" aria-label="Adelantar 15 segundos" onClick={() => skip(15)}>
            <RotateCw size={17} />
            <i>15</i>
          </button>
          <span className="player__time">
            {fmt(shownTime)} / {fmt(duration)}
          </span>

          <span className="player__spacer" />

          <div className="player__vol">
            <button type="button" className="player__btn" aria-label={muted ? 'Activar sonido' : 'Silenciar'} onClick={toggleMute}>
              {muted || volume === 0 ? <VolumeX size={17} /> : <Volume2 size={17} />}
            </button>
            <input
              type="range"
              min={0}
              max={100}
              value={muted ? 0 : volume}
              onChange={e => changeVolume(Number(e.target.value))}
              aria-label="Volumen"
            />
          </div>

          <button
            type="button"
            className="player__btn"
            aria-label={full ? 'Salir de pantalla completa' : 'Pantalla completa'}
            onClick={toggleFull}
          >
            {full ? <Minimize size={17} /> : <Maximize size={17} />}
          </button>
        </div>
      </div>
    </div>
  );
}
