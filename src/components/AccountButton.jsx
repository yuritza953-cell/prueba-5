import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Bookmark, LogIn, LogOut, ShieldCheck, X } from 'lucide-react';
import { preloadGoogleIdentity, useAuth } from '../lib/auth';
import { useT } from '../i18n';
import './AccountButton.css';

const initialsOf = name =>
  String(name || 'K')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part.charAt(0))
    .join('')
    .toUpperCase() || 'K';

function Avatar({ user, className = '' }) {
  const [broken, setBroken] = useState(false);

  useEffect(() => {
    setBroken(false);
  }, [user?.avatar]);

  return (
    <span className={`account__avatar-ui${className ? ` ${className}` : ''}`} aria-hidden="true">
      {user?.avatar && !broken ? (
        <img src={user.avatar} alt="" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
      ) : (
        <span className="account__initials">{initialsOf(user?.name)}</span>
      )}
    </span>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true" focusable="false">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"
      />
    </svg>
  );
}

function DiscordMark() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M20.317 4.37a19.79 19.79 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.372-.291a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.099.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.182 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  );
}

function LoginDialog({ open, onClose }) {
  const t = useT();
  const { busy, signInWithGoogle, signInWithDiscord } = useAuth();
  const [error, setError] = useState('');
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    setError('');
    preloadGoogleIdentity();
    const timer = window.setTimeout(() => closeRef.current?.focus(), 30);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = event => {
      if (event.key === 'Escape' && !busy) onClose();
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, busy, onClose]);

  if (!open) return null;

  const messageFor = (caught, provider) => {
    if (caught?.code === 'missing_config') {
      return t('auth.errors.config', { provider: provider === 'google' ? 'Google' : 'Discord' });
    }
    if (caught?.code === 'popup_blocked') return t('auth.errors.popup');
    if (caught?.code === 'cancelled') return t('auth.errors.cancelled');
    return t('auth.errors.generic');
  };

  const start = async provider => {
    setError('');
    try {
      if (provider === 'google') await signInWithGoogle();
      else await signInWithDiscord();
      onClose();
    } catch (caught) {
      if (import.meta.env.DEV) console.warn('[auth]', caught);
      setError(messageFor(caught, provider));
    }
  };

  return createPortal(
    <div
      className="auth"
      onMouseDown={event => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <section
        className="auth__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        aria-describedby="auth-subtitle"
      >
        <button
          ref={closeRef}
          type="button"
          className="auth__close"
          onClick={onClose}
          disabled={Boolean(busy)}
          aria-label={t('common.close')}
        >
          <X size={17} />
        </button>

        <div className="auth__mark" aria-hidden="true">
          <img src="/assets/kinora-logo.svg" alt="" width={24} height={24} />
        </div>

        <h2 id="auth-title" className="auth__title">
          {t('auth.title')}
        </h2>
        <p id="auth-subtitle" className="auth__text">
          {t('auth.subtitle')}
        </p>

        <div className="auth__providers">
          <button
            type="button"
            className="auth__provider auth__provider--google"
            onClick={() => start('google')}
            disabled={Boolean(busy)}
          >
            {busy === 'google' ? <span className="auth__spinner auth__spinner--dark" /> : <GoogleMark />}
            <span>{busy === 'google' ? t('auth.connecting') : t('auth.continueGoogle')}</span>
          </button>

          <button
            type="button"
            className="auth__provider auth__provider--discord"
            onClick={() => start('discord')}
            disabled={Boolean(busy)}
          >
            {busy === 'discord' ? <span className="auth__spinner" /> : <DiscordMark />}
            <span>{busy === 'discord' ? t('auth.connecting') : t('auth.continueDiscord')}</span>
          </button>
        </div>

        {error ? (
          <p className="auth__error" role="alert">
            {error}
          </p>
        ) : null}

        <p className="auth__note">
          <ShieldCheck size={14} />
          {t('auth.privacy')}
        </p>
      </section>
    </div>,
    document.body
  );
}

export default function AccountButton({ onList, className = '' }) {
  const t = useT();
  const { user, provider, signOut } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onPointer = event => {
      if (!rootRef.current?.contains(event.target)) setMenuOpen(false);
    };
    document.addEventListener('pointerdown', onPointer);
    return () => document.removeEventListener('pointerdown', onPointer);
  }, [menuOpen]);

  useEffect(() => {
    if (!user) setMenuOpen(false);
  }, [user]);

  const providerLabel = provider === 'google' ? 'Google' : provider === 'discord' ? 'Discord' : '';

  const openList = () => {
    setMenuOpen(false);
    onList?.();
  };

  const logout = () => {
    setMenuOpen(false);
    signOut();
  };

  return (
    <div className={`account${className ? ` ${className}` : ''}`} ref={rootRef}>
      {user ? (
        <button
          type="button"
          className="account__avatar"
          onClick={() => setMenuOpen(open => !open)}
          aria-label={t('auth.account')}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          title={user.name}
        >
          <Avatar user={user} />
        </button>
      ) : (
        <button
          type="button"
          className="account__login"
          onClick={() => setLoginOpen(true)}
          aria-label={t('auth.login')}
          title={t('auth.login')}
        >
          <LogIn size={16} strokeWidth={2.3} />
          <span className="account__login-label">{t('auth.login')}</span>
        </button>
      )}

      {menuOpen && user ? (
        <div className="account__menu" role="menu" aria-label={t('auth.account')}>
          <div className="account__identity">
            <Avatar user={user} className="account__avatar-ui--menu" />
            <div className="account__identity-copy">
              <strong>{user.name}</strong>
              {user.email ? <span>{user.email}</span> : null}
              <em>{t('auth.connectedWith', { provider: providerLabel })}</em>
            </div>
          </div>

          <div className="account__menu-actions">
            <button type="button" role="menuitem" onClick={openList}>
              <Bookmark size={15} />
              {t('auth.viewList')}
            </button>
            <button type="button" role="menuitem" className="account__logout" onClick={logout}>
              <LogOut size={15} />
              {t('auth.logout')}
            </button>
          </div>
        </div>
      ) : null}

      <LoginDialog open={loginOpen} onClose={() => setLoginOpen(false)} />
    </div>
  );
}
