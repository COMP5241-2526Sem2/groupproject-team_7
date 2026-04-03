import React from 'react';
import '../styles/Header.css';

function Header({ view, onViewChange }) {
  return (
    <header className="header">
      <div className="header-left">
        <span className="header-logo">SL</span>
        <span className="header-title">Sync Learn</span>
        <span className="header-subtitle">· Multimodal AI Smart Review</span>
      </div>
      <nav className="header-nav">
        <button
          className={`nav-btn ${view === 'learn' ? 'active' : ''}`}
          onClick={() => onViewChange('learn')}
        >
          Learn
        </button>
        <button
          className={`nav-btn ${view === 'dashboard' ? 'active' : ''}`}
          onClick={() => onViewChange('dashboard')}
        >
          Dashboard
        </button>
      </nav>
    </header>
  );
}

export default Header;
