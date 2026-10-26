import { ArrowUpRight, Check, Play } from 'lucide-react';
import { useState } from 'react';
import { useT } from '../i18n';
import { openCookiePreferences } from '../lib/cookies';
import './Footer.css';

export default function Footer({ onHome, onList, onBrowse, onShuffle }) {
  const t = useT();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  const submit = event => {
    event.preventDefault();
    if (!email.trim()) return;
    setSent(true);
    setEmail('');
  };

  return (
    <footer className="foot">
      <div className="shell foot__inner">
        <section className="foot__cta">
          <div className="foot__cta-copy">
            <span className="eyebrow">Kinora</span>
            <h2 className="foot__cta-title">{t('footer.ctaTitle')}</h2>
            <p className="foot__cta-text">{t('footer.ctaText')}</p>
          </div>
          <button type="button" className="foot__cta-btn" onClick={onShuffle}>
            <Play size={15} fill="currentColor" strokeWidth={0} />
            {t('footer.ctaBtn')}
            <ArrowUpRight size={15} />
          </button>
        </section>

        <div className="foot__grid">
          <form className="foot__news" onSubmit={submit}>
            <h3>{t('footer.newsTitle')}</h3>
            <p>{t('footer.newsText')}</p>
            <label className="foot__field">
              <span className="foot__field-label">{t('footer.email')}</span>
              <span className="foot__field-row">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={event => {
                    setEmail(event.target.value);
                    setSent(false);
                  }}
                  placeholder="you@example.com"
                  aria-label={t('footer.email')}
                />
                <button type="submit" className={sent ? 'is-sent' : undefined}>
                  {sent ? <Check size={14} /> : null}
                  {sent ? t('footer.subscribed') : t('footer.subscribe')}
                </button>
              </span>
            </label>
          </form>

          <nav className="foot__col" aria-label={t('footer.explore')}>
            <h3>{t('footer.explore')}</h3>
            <button type="button" onClick={onHome}>
              {t('footer.home')}
            </button>
            <button type="button" onClick={() => onBrowse?.('movie')}>
              {t('footer.movies')}
            </button>
            <button type="button" onClick={() => onBrowse?.('tv')}>
              {t('footer.series')}
            </button>
            <button type="button" onClick={onList}>
              {t('footer.list')}
            </button>
          </nav>

          <nav className="foot__col" aria-label={t('footer.legal')}>
            <h3>{t('footer.legal')}</h3>
            <a href="/privacy.html">{t('footer.privacy')}</a>
            <a href="/terms.html">{t('footer.terms')}</a>
            <button type="button" className="foot__linkish" onClick={openCookiePreferences}>
              Cookies
            </button>
            <a href="mailto:contact@kinora.com.co">contact@kinora.com.co</a>
          </nav>
        </div>

        <div className="foot__bottom">
          <span className="foot__logo">
            <img src="/assets/kinora-logo.svg" alt="" width={18} height={18} />
            {t('footer.rights')}
          </span>
          <span className="foot__tagline">{t('footer.tagline')}</span>
        </div>
      </div>
    </footer>
  );
}