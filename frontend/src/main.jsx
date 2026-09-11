import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import { istemciHataApi } from './api.js';
import { globalYakalayicilariBagla } from './lib/hataBildir.js';

// BUG #406 (OBS-013): yakalanmamış hata ve promise reddi sunucu hata defterine düşer.
globalYakalayicilariBagla(istemciHataApi.bildir);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);