import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import IngestionInterface from './components/IngestionInterface';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="nav-brand">
            <div className="brand-logo">GenAI</div>
            <div className="brand-text">
              <span className="brand-title">DevOps Assistant</span>
              <span className="brand-subtitle">AI-Powered Infrastructure Support</span>
            </div>
          </div>
          <div className="nav-links">
            <Link to="/" className="nav-link">Chat</Link>
            <Link to="/ingest" className="nav-link">Document Ingestion</Link>
          </div>
        </nav>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<ChatInterface />} />
            <Route path="/ingest" element={<IngestionInterface />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;