import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Privacy from './Privacy';
import './Privacy.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Privacy />
  </StrictMode>
);
