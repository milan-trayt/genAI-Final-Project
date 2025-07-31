import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import IngestionInterface from './components/IngestionInterface';
import './App.css';

function NavBar() {
  const location = useLocation();
  
  return (
    <nav className="navbar">
      <div className="nav-brand">
        <div className="brand-logo">GenAI</div>
        <div className="brand-text">
          <span className="brand-title">DevOps Assistant</span>
          <span className="brand-subtitle">AI-Powered Infrastructure Support</span>
        </div>
      </div>
      <div className="nav-links">
        <Link 
          to="/" 
          className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
        >
          Chat
        </Link>
        <Link 
          to="/ingest" 
          className={`nav-link ${location.pathname === '/ingest' ? 'active' : ''}`}
        >
          Document Ingestion
        </Link>
      </div>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="app">
        <NavBar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<ChatInterface />} />
            <Route path="/ingest" element={<IngestionInterface />} />
            <Route path="*" element={<ChatInterface />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;