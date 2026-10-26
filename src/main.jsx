import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { I18nProvider } from './i18n';
import { applyConsentSideEffects, readConsent } from './lib/cookies';

const existing = readConsent();
if (existing) applyConsentSideEffects(existing);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </StrictMode>
);