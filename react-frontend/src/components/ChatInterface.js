import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { Send, Plus, X, Settings } from 'lucide-react';
import QueryTypeSelector from './QueryTypeSelector';
import '../QueryTypeSelector.css';

const ChatInterface = () => {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [quickResponse, setQuickResponse] = useState('');
  const [showQuickModal, setShowQuickModal] = useState(false);
  const [quickResult, setQuickResult] = useState('');
  const [queryType, setQueryType] = useState('general');

  const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [sessions]);

  const loadSessions = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/sessions`);
      const sessionData = await Promise.all(
        response.data.sessions.map(async (session) => {
          // Load messages for each session
          try {
            const historyResponse = await axios.get(`${API_BASE_URL}/sessions/${session.session_id}/history`);
            return {
              id: session.session_id,
              name: session.session_name,
              sessionId: session.session_id,
              messages: historyResponse.data.messages || [],
              createdAt: session.created_at,
              updatedAt: session.updated_at
            };
          } catch (error) {
            console.error(`Failed to load history for session ${session.session_id}:`, error);
            return {
              id: session.session_id,
              name: session.session_name,
              sessionId: session.session_id,
              messages: [],
              createdAt: session.created_at,
              updatedAt: session.updated_at
            };
          }
        })
      );
      setSessions(sessionData);
      setIsInitialized(true);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const createNewSession = async () => {
    try {
      const sessionName = 'New Session';
      const response = await axios.post(`${API_BASE_URL}/sessions`, {
        session_name: sessionName
      });
      
      const newSession = {
        id: response.data.session_id,
        name: sessionName,
        sessionId: response.data.session_id,
        messages: [],
        createdAt: response.data.created_at
      };
      
      setSessions([...sessions, newSession]);
      setActiveSession(response.data.session_id);
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const deleteSession = async (sessionId) => {
    try {
      await axios.delete(`${API_BASE_URL}/sessions/${sessionId}`);
      const newSessions = sessions.filter(s => s.id !== sessionId);
      setSessions(newSessions);
      
      if (activeSession === sessionId) {
        setActiveSession(newSessions.length > 0 ? newSessions[0].id : null);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const updateSessionName = async (sessionId, firstQuery) => {
    try {
      // Generate topic from first query
      const topicResponse = await axios.post(`${API_BASE_URL}/generate-topic`, {
        query: firstQuery
      });
      
      const newName = topicResponse.data.topic;
      
      // Update session name in backend
      await axios.put(`${API_BASE_URL}/sessions/${sessionId}`, {
        session_name: newName
      });
      
      // Update local state
      setSessions(prevSessions => 
        prevSessions.map(session => 
          session.sessionId === sessionId 
            ? { ...session, name: newName }
            : session
        )
      );
    } catch (error) {
      console.error('Failed to update session name:', error);
    }
  };

  const loadSessionHistory = async (sessionId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/sessions/${sessionId}/history`);
      setSessions(prevSessions => 
        prevSessions.map(session => 
          session.id === sessionId 
            ? { ...session, messages: response.data.messages || [] }
            : session
        )
      );
    } catch (error) {
      console.error('Failed to load session history:', error);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  // Remove this useEffect since we now load history during initial session loading



  const sendMessage = async () => {
    if (!input.trim() || isLoading || !activeSession) return;

    const currentSession = sessions.find(s => s.id === activeSession);
    if (!currentSession) return;

    const userMessage = { role: 'user', content: input };
    
    // Add user message
    setSessions(prevSessions => 
      prevSessions.map(session => 
        session.id === activeSession 
          ? { ...session, messages: [...session.messages, userMessage] }
          : session
      )
    );
    
    const queryText = input;
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/query/conversational`, {
        query: queryText,
        session_id: currentSession.sessionId,
        query_type: queryType
      });

      const assistantMessage = {
        role: 'assistant',
        content: response.data.response,
        query_type: response.data.query_type,
        metadata: response.data.metadata
      };

      // Check if guardrail was triggered and if this is the first message
      const isGuardrailResponse = response.data.response.includes('I can only help with AWS cloud infrastructure');
      const isFirstUserMessage = currentSession.messages.length === 0;
      
      if (isGuardrailResponse && isFirstUserMessage) {
        // Delete the session only if it's the first message
        try {
          await axios.delete(`${API_BASE_URL}/sessions/${currentSession.sessionId}`);
          const newSessions = sessions.filter(s => s.id !== activeSession);
          setSessions(newSessions);
          setActiveSession(null);
        } catch (error) {
          console.error('Failed to delete session:', error);
        }
      } else {
        setSessions(prevSessions => 
          prevSessions.map(session => 
            session.id === activeSession 
              ? { ...session, messages: [...session.messages, assistantMessage] }
              : session
          )
        );
      }

      // Update session name after first message if it's still default
      const isFirstMessage = currentSession.messages.length === 0; // No messages before this one
      console.log('Session name update check:', {
        isFirstMessage,
        sessionName: currentSession.name,
        messageCount: currentSession.messages.length
      });
      
      if (isFirstMessage && currentSession.name === 'New Session') {
        console.log('Updating session name for:', currentSession.sessionId);
        updateSessionName(currentSession.sessionId, queryText);
      }
    } catch (error) {
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, there was an error processing your request.',
        error: true
      };
      
      setSessions(prevSessions => 
        prevSessions.map(session => 
          session.id === activeSession 
            ? { ...session, messages: [...session.messages, errorMessage] }
            : session
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const sendQuickQuery = async () => {
    if (!quickResponse.trim() || isLoading) return;

    setIsLoading(true);
    setQuickResult('');

    try {
      const response = await axios.post(`${API_BASE_URL}/query/one-time`, {
        query: quickResponse,
        query_type: queryType
      });

      setQuickResult(response.data.response);
    } catch (error) {
      setQuickResult('Error getting quick response. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const closeQuickModal = () => {
    setShowQuickModal(false);
    setQuickResponse('');
    setQuickResult('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  const getPlaceholderText = () => {
    switch(queryType) {
      case 'service_recommendation':
        return 'Describe your use case and get AWS service recommendations with step-by-step reasoning...';
      case 'pricing':
        return 'Ask about AWS pricing estimates for specific services and usage patterns...';
      case 'terraform':
        return 'Request Terraform code for AWS infrastructure deployment...';
      default:
        return 'Ask about AWS services, architecture, or cloud infrastructure...';
    }
  };

  const activeSessionData = sessions.find(s => s.id === activeSession);

  return (
    <div className="chat-interface">
      <div className="chat-sidebar">
        <div className="sidebar-header">
          <h3>💬 Chat Sessions</h3>
          <button onClick={createNewSession} className="new-session">
            <Plus size={16} /> New Chat
          </button>
        </div>

        <div className="sessions-list">
          {sessions.map(session => (
            <div key={session.id} className={`session-item ${activeSession === session.id ? 'active' : ''}`}>
              <button 
                onClick={() => setActiveSession(session.id)} 
                className="session-button"
              >
                {session.name}
              </button>
              <button 
                onClick={() => deleteSession(session.id)} 
                className="close-session"
                title="Delete session"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="quick-response-section">
          <button 
            onClick={() => setShowQuickModal(true)}
            className="quick-modal-button"
          >
            ⚡ Quick Response
          </button>
        </div>
      </div>

      <div className="chat-main">
        {!activeSession ? (
          <div className="no-session">
            <h2>AWS Cloud Infrastructure Assistant</h2>
            <p>Get AWS service recommendations, pricing estimates, and Terraform code generation with step-by-step reasoning.</p>
            <div className="features-grid">
              <div className="feature-card">
                <h3>Service Recommendations</h3>
                <p>Get personalized AWS service recommendations based on your specific use case with detailed reasoning.</p>
              </div>
              <div className="feature-card">
                <h3>Pricing Estimates</h3>
                <p>Receive cost estimates and optimization tips for your AWS infrastructure.</p>
              </div>
              <div className="feature-card">
                <h3>Terraform Code</h3>
                <p>Generate production-ready Terraform configurations for your AWS resources.</p>
              </div>
            </div>
            {sessions.length > 0 && (
              <div className="session-indicators">
                <h3>📊 Current Sessions: {sessions.length}</h3>
                <div className="session-list">
                  {sessions.map(session => (
                    <div key={session.id} className="session-indicator">
                      <span className="session-name">{session.name}</span>
                      <span className="session-date">
                        {new Date(session.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="chat-messages">
              {activeSessionData?.messages.map((message, index) => (
                <div key={index} className={`message ${message.role}`}>
                  <div className="message-content">
                    {message.query_type && message.query_type !== 'general' && (
                      <div className="message-type-badge">
                        {message.query_type.replace('_', ' ').toUpperCase()}
                      </div>
                    )}
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                    {message.metadata?.terraform_code && (
                      <div className="terraform-code">
                        <h4>Generated Terraform Code:</h4>
                        <pre><code>{message.metadata.terraform_code}</code></pre>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="message assistant">
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
              <QueryTypeSelector 
                queryType={queryType}
                setQueryType={setQueryType}
              />
              <div className="chat-input">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={getPlaceholderText()}
                  disabled={isLoading}
                  rows={3}
                />
                <button onClick={sendMessage} disabled={isLoading || !input.trim()}>
                  <Send size={20} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Quick Response Modal */}
      {showQuickModal && (
        <div className="modal-overlay" onClick={closeQuickModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚡ Quick Response</h3>
              <button onClick={closeQuickModal} className="modal-close">
                <X size={20} />
              </button>
            </div>
            
            <div className="modal-body">
              <textarea
                value={quickResponse}
                onChange={(e) => setQuickResponse(e.target.value)}
                placeholder="Ask a quick question without creating a session..."
                rows={4}
                className="quick-textarea"
              />
              
              <div className="modal-actions">
                <button 
                  onClick={sendQuickQuery} 
                  disabled={!quickResponse.trim() || isLoading}
                  className="quick-submit"
                >
                  {isLoading ? (
                    <>
                      <div className="spinner"></div>
                      Processing...
                    </>
                  ) : (
                    '⚡ Ask'
                  )}
                </button>
              </div>
              
              {quickResult && (
                <div className="quick-result">
                  <h4>Response:</h4>
                  <div className="result-content">
                    <ReactMarkdown>{quickResult}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;