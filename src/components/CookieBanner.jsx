import { useEffect, useState } from 'react';
import {
  acceptAll,
  hasAnsweredConsent,
  readConsent,
  rejectNonEssential,
  saveConsent,
} from '../lib/cookies';
import './CookieBanner.css';

export default function CookieBanner() {
  const [visible, setVisible] = useState(false);
  const [panel, setPanel] = useState(false); // configuración avanzada
  const [analytics, setAnalytics] = useState(false);
  const [advertising, setAdvertising] = useState(false);

  useEffect(() => {
    const existing = readConsent();
    if (existing) {
      setAnalytics(Boolean(existing.analytics));
      setAdvertising(Boolean(existing.advertising));
    }
    if (!hasAnsweredConsent()) setVisible(true);

    const onOpen = () => {
      const c = readConsent();
      if (c) {
        setAnalytics(Boolean(c.analytics));
        setAdvertising(Boolean(c.advertising));
      }
      setPanel(true);
      setVisible(true);
    };
    window.addEventListener('kinora:open-cookies', onOpen);
    return () => window.removeEventListener('kinora:open-cookies', onOpen);
  }, []);

  if (!visible) return null;

  const close = () => {
    setVisible(false);
    setPanel(false);
  };

  const onAcceptAll = () => {
    acceptAll();
    close();
  };

  const onReject = () => {
    rejectNonEssential();
    close();
  };

  const onSaveConfig = () => {
    saveConsent({ analytics, advertising: true }); // inventario siempre activo
    close();
  };

  return (
    <div className="ck" role="dialog" aria-labelledby="ck-title" aria-modal="false">
      <div className="ck__card">
        <div className="ck__head">
          <h2 id="ck-title" className="ck__title">
            Cookies y privacidad
          </h2>
          <p className="ck__text">
            Usamos cookies propias y de terceros, y almacenamiento local, para el funcionamiento del
            sitio y preferencias. Puede mostrarse publicidad contextual o de red sin aceptar cookies
            de marketing; la publicidad personalizada y la medición analítica solo si lo autorizas.
            Puedes aceptar, rechazar lo no esencial o configurar. Más detalle en la{' '}
            <a href="/privacy.html" target="_blank" rel="noopener noreferrer">
              Política de Privacidad
            </a>
            .
          </p>
        </div>

        {panel ? (
          <div className="ck__config">
            <label className="ck__row">
              <span>
                <strong>Estrictamente necesarias</strong>
                <small>Seguridad, sesión básica y recuerdo de tu elección. Siempre activas.</small>
              </span>
              <input type="checkbox" checked disabled readOnly />
            </label>
            <label className="ck__row">
              <span>
                <strong>Preferencias</strong>
                <small>Idioma, listas y caché de subtítulos en tu dispositivo.</small>
              </span>
              <input type="checkbox" checked disabled readOnly />
            </label>
            <label className="ck__row">
              <span>
                <strong>Analítica</strong>
                <small>Estadísticas de uso agregadas (cuando esté habilitada).</small>
              </span>
              <input
                type="checkbox"
                checked={analytics}
                onChange={e => setAnalytics(e.target.checked)}
              />
            </label>
          </div>
        ) : null}

        <div className="ck__actions">
          {panel ? (
            <>
              <button type="button" className="ck__btn ck__btn--ghost" onClick={() => setPanel(false)}>
                Volver
              </button>
              <button type="button" className="ck__btn ck__btn--primary" onClick={onSaveConfig}>
                Guardar preferencias
              </button>
            </>
          ) : (
            <>
              <button type="button" className="ck__btn ck__btn--ghost" onClick={onReject}>
                Rechazar no esenciales
              </button>
              <button type="button" className="ck__btn ck__btn--ghost" onClick={() => setPanel(true)}>
                Configurar
              </button>
              <button type="button" className="ck__btn ck__btn--primary" onClick={onAcceptAll}>
                Aceptar todas
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}