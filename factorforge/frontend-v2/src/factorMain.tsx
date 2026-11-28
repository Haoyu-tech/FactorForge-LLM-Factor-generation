import React from 'react';
import ReactDOM from 'react-dom/client';
import { LanguageProvider } from '@/context/LanguageContext';
import { FactorPage } from '@/pages/FactorPage';
import './index.css';

// Entry for factor.html: one factor's full detail on its own page.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LanguageProvider>
      <FactorPage />
    </LanguageProvider>
  </React.StrictMode>
);
