import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Terms from './Terms';
import './Terms.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Terms />
  </StrictMode>
);
