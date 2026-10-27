import { useCallback, useEffect } from 'react';
import { Bookmark, ChevronLeft } from 'lucide-react';
import AccountButton from './AccountButton';
import AdSlot from './AdSlot';
import PromptBar from './PromptBar';
import { AD_SLOTS } from '../lib/ads';
import { useT } from '../i18n';
import './TopBar.css';

export default function TopBar({
  onHome,
  onBack,
  onSearch,
  onStop,
  busy,
  onList,
  savedCount = 0,
  dubLang,
  onDubLangChange,
  showMobileAd = false
}) {
  const t = useT();

  // El banner móvil vive encima de la barra fija: cuando aparece, el pie de
  // página necesita más aire para no quedar tapado por ambos.
  useEffect(() => {
    if (!showMobileAd) return undefined;
    return () => document.documentElement.style.removeProperty('--k-bottom-ad');
  }, [showMobileAd]);

  // Estable: si cambia en cada render, AdSlot vuelve a inyectar el tag.
  const handleAdFill = useCallback(filled => {
    document.documentElement.style.setProperty('--k-bottom-ad', filled ? '112px' : '0px');
  }, []);

  return (
    <header className="topbar">
      <div className="topbar__brand">
        <button type="button" className="topbar__back" onClick={onBack} aria-label={t('nav.back')} title={t('nav.back')}>
          <ChevronLeft size={22} strokeWidth={2.4} />
        </button>
        <button type="button" className="topbar__logo" onClick={onHome} aria-label="Kinora">
          <img src="/assets/kinora-logo.svg" alt="" width={22} height={22} className="topbar__mark" />
          Kinora
        </button>
      </div>

      <div className="topbar__search">
        {showMobileAd ? (
          <div className="topbar__ad">
            <AdSlot
              src={AD_SLOTS.mobile}
              format="mobile"
              media="(max-width: 900px)"
              label={t('player.ad')}
              onFillChange={handleAdFill}
            />
          </div>
        ) : null}
        <PromptBar
          placeholder={t('search.placeholder')}
          sources={[]}
          commands={[]}
          busy={busy}
          onSend={onSearch}
          onStop={onStop}
          dropDown
          collapsed
          width={660}
          radius={16}
          background="rgba(21, 60, 168, 0.72)"
          menuBackground="rgba(7, 24, 92, 0.94)"
          color="#eaf2ff"
          sparkColor="#8ab8ff"
          className="topbar__prompt"
          lang={dubLang}
          onLangChange={onDubLangChange}
        />
      </div>

      <div className="topbar__actions">
        <button type="button" className="topbar__icon" onClick={onList} aria-label={t('nav.list')} title={t('nav.list')}>
          <Bookmark size={18} />
          {savedCount > 0 ? <span className="topbar__count">{savedCount > 9 ? '9+' : savedCount}</span> : null}
        </button>
        <AccountButton onList={onList} />
      </div>
    </header>
  );
}
