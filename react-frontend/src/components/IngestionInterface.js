import React, { useState, useCallback } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Github, Globe, Trash2, Play, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import io from 'socket.io-client';

const IngestionInterface = () => {
  const [sources, setSources] = useState(() => {
    const saved = localStorage.getItem('ingestionSources');
    return saved ? JSON.parse(saved) : [];
  });
  const [isProcessing, setIsProcessing] = useState(() => {
    return localStorage.getItem('isProcessing') === 'true';
  });
  const [processingStep, setProcessingStep] = useState(() => {
    return localStorage.getItem('processingStep') || '';
  });
  const [processingDetails, setProcessingDetails] = useState(() => {
    const saved = localStorage.getItem('processingDetails');
    return saved ? JSON.parse(saved) : [];
  });
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('activeTab') || 'web';
  });
  const [error, setError] = useState(() => {
    return localStorage.getItem('processingError') || null;
  });
  const [success, setSuccess] = useState(() => {
    return localStorage.getItem('processingSuccess') === 'true';
  });
  const [processingComplete, setProcessingComplete] = useState(() => {
    return localStorage.getItem('processingComplete') === 'true';
  });
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [connectionMessage, setConnectionMessage] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState(null);

  const COLLAB_URL = process.env.REACT_APP_COLLAB_URL || 'http://localhost:8503';


  const addSource = (source) => {
    setSources(prevSources => {
      const newSources = [...prevSources, { ...source, id: Date.now() + Math.random() }];
      localStorage.setItem('ingestionSources', JSON.stringify(newSources));
      return newSources;
    });
  };

  const removeSource = (id) => {
    const newSources = sources.filter(s => s.id !== id);
    setSources(newSources);
    localStorage.setItem('ingestionSources', JSON.stringify(newSources));
  };

  const clearSources = () => {
    setSources([]);
    localStorage.removeItem('ingestionSources');
  };

  const startPollingFallback = async (sessionId) => {
    let pollCount = 0;
    const maxPolls = 60; // Poll for up to 5 minutes (60 * 5s intervals)
    
    setProcessingDetails(prev => [...prev, 'WebSocket failed, switching to polling mode...']);
    
    const poll = async () => {
      try {
        // Check if processing is still active by trying to get status
        const response = await axios.get(`${COLLAB_URL}/api/status`);
        
        if (response.data.status === 'ready') {
          setProcessingDetails(prev => [...prev, `Polling for status updates... (${pollCount + 1}/${maxPolls})`]);
          
          pollCount++;
          if (pollCount < maxPolls && isProcessing) {
            setTimeout(poll, 5000); // Poll every 5 seconds
          } else if (pollCount >= maxPolls) {
            setError('Processing timeout - no updates received after 5 minutes');
            setProcessingStep('Processing timeout');
            setIsProcessing(false);
            setProcessingComplete(true);
          }
        } else {
          // Processing might be complete, check one more time
          setProcessingDetails(prev => [...prev, 'Processing appears to be complete']);
          setSuccess(true);
          setProcessingStep('Processing completed (detected via polling)');
          setIsProcessing(false);
          setProcessingComplete(true);
        }
      } catch (error) {
        setError('Failed to connect to processing server');
        setProcessingStep('Connection failed');
        setIsProcessing(false);
        setProcessingComplete(true);
      }
    };
    
    // Start polling after a short delay
    setTimeout(poll, 2000);
  };

  const processDocuments = async () => {
    if (sources.length === 0) return;
    
    setIsProcessing(true);
    setProcessingDetails([]);
    setProcessingStep('Connecting to WebSocket...');
    setError(null);
    setSuccess(false);
    setProcessingComplete(false);
    
    localStorage.setItem('isProcessing', 'true');
    localStorage.setItem('processingDetails', JSON.stringify([]));
    localStorage.setItem('processingStep', 'Connecting to WebSocket...');
    localStorage.removeItem('processingError');
    localStorage.setItem('processingSuccess', 'false');
    localStorage.setItem('processingComplete', 'false');
    
    const sessionId = `session_${Date.now()}`;
    setCurrentSessionId(sessionId);
    
    // Connect to WebSocket with full transport capabilities
    const socket = io(COLLAB_URL, {
      transports: ['polling', 'websocket'],  // Allow both transports
      timeout: 30000,
      pingTimeout: 120000,
      pingInterval: 30000,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      forceNew: true,
      autoConnect: true,
      upgrade: true,  // Enable upgrade to websocket
      rememberUpgrade: true,
      query: {
        session_id: sessionId  // Pass session ID in query for better tracking
      }
    });
    
    socket.on('connect', () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
      setConnectionMessage('Connected to processing server');
      setProcessingStep('Connected, joining room...');
      socket.emit('join_session', { session_id: sessionId });
      
      // Set a timeout to disconnect if no response
      setTimeout(() => {
        if (!processingStarted) {
          console.log('No response received, disconnecting');
          setConnectionStatus('error');
          setConnectionMessage('Connection timeout - no response from server');
          setProcessingStep('Connection timeout');
          setError('WebSocket connection timeout');
          setIsProcessing(false);
          setProcessingComplete(true);
          socket.disconnect();
        }
      }, 10000);
    });
    
    let processingStarted = false;
    
    socket.on('joined', async (data) => {
      console.log('Joined room:', data.session_id);
      if (processingStarted) return;
      processingStarted = true;
      
      setProcessingStep('Starting processing...');
      
      await new Promise(resolve => setTimeout(resolve, 500));
      
      try {
        const processingSources = sources.map(source => ({
          type: source.type,
          name: source.name,
          path: source.path,
          docType: source.docType || 'document',
          token: source.token,
          extensions: source.extensions,
          priority: source.priority,
          category: source.category,
          tags: source.tags,
          customMetadata: source.customMetadata,
          ...source
        }));
        
        const inputData = JSON.stringify({
          sources: processingSources,
          batch_size: Math.min(3, sources.length)
        });
        
        await axios.post(`${COLLAB_URL}/api/process`, {
          input: inputData,
          session_id: sessionId
        });
        
      } catch (error) {
        setIsProcessing(false);
        setProcessingComplete(true);
        const errorMessage = error.response?.data?.message || error.message || 'Network error occurred';
        setProcessingStep('Connection failed');
        setProcessingDetails(prev => [...prev, `Error: ${errorMessage}`]);
        setError(errorMessage);
        socket.disconnect();
      }
    });
    
    socket.on('processing_update', (data) => {
      console.log('RECEIVED processing_update:', data);
      
      if (data.type === 'log') {
        setProcessingDetails(prev => {
          const newDetails = [...prev, data.message];
          localStorage.setItem('processingDetails', JSON.stringify(newDetails));
          return newDetails;
        });
        setProcessingStep(data.message);
        localStorage.setItem('processingStep', data.message);
      } else if (data.type === 'progress') {
        setProcessingDetails(prev => {
          const newDetails = [...prev, data.message];
          localStorage.setItem('processingDetails', JSON.stringify(newDetails));
          return newDetails;
        });
        setProcessingStep(data.message);
        localStorage.setItem('processingStep', data.message);
        // Could add progress bar here if needed
      } else if (data.type === 'complete') {
        // Only mark as complete if this is the final completion (all sources processed)
        if (data.final === true || data.all_complete === true) {
          setIsProcessing(false);
          setProcessingComplete(true);
          localStorage.setItem('isProcessing', 'false');
          localStorage.setItem('processingComplete', 'true');
          
          if (data.status === 'success') {
            setSuccess(true);
            setProcessingStep('Processing completed successfully!');
            localStorage.setItem('processingSuccess', 'true');
            localStorage.setItem('processingStep', 'Processing completed successfully!');
            
            // Add final stats if available
            if (data.data?.stats) {
              const stats = data.data.stats;
              const statsDetails = [
                `Final Statistics:`,
                `   • Total sources: ${stats.total_sources}`,
                `   • Processing time: ${stats.processing_time?.toFixed(2)}s`
              ];
              setProcessingDetails(prev => {
                const newDetails = [...prev, ...statsDetails];
                localStorage.setItem('processingDetails', JSON.stringify(newDetails));
                return newDetails;
              });
            }
          } else {
            const errorMsg = data.message || 'Processing failed';
            setError(errorMsg);
            setProcessingStep('Processing failed');
            localStorage.setItem('processingError', errorMsg);
            localStorage.setItem('processingStep', 'Processing failed');
          }
          socket.disconnect();
        } else {
          // Individual source completed, just log it
          setProcessingDetails(prev => {
            const newDetails = [...prev, data.message || 'Source completed'];
            localStorage.setItem('processingDetails', JSON.stringify(newDetails));
            return newDetails;
          });
          if (data.message) {
            setProcessingStep(data.message);
            localStorage.setItem('processingStep', data.message);
          }
        }
      } else if (data.type === 'error') {
        setIsProcessing(false);
        setProcessingComplete(true);
        setError(data.message || 'Processing error occurred');
        setProcessingStep('Processing failed');
        localStorage.setItem('processingError', data.message || 'Processing error occurred');
        localStorage.setItem('processingStep', 'Processing failed');
        if (data.details) {
          setProcessingDetails(prev => {
            const newDetails = [...prev, `Error details: ${data.details}`];
            localStorage.setItem('processingDetails', JSON.stringify(newDetails));
            return newDetails;
          });
        }
        socket.disconnect();
      }
    });
    
    socket.on('connect_error', (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
      setConnectionMessage('WebSocket connection failed, falling back to polling');
      setProcessingStep('WebSocket failed, using polling fallback...');
      
      // Start fallback polling
      startPollingFallback(sessionId);
    });
    
    socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setConnectionStatus('disconnected');
      setConnectionMessage(`Disconnected: ${reason}`);
      
      if (reason === 'ping timeout' && !processingComplete) {
        setProcessingStep('Connection lost, attempting to reconnect...');
      }
    });
    
    socket.on('reconnect', (attemptNumber) => {
      console.log('WebSocket reconnected after', attemptNumber, 'attempts');
      setConnectionStatus('connected');
      setConnectionMessage('Reconnected to processing server');
      setProcessingStep('Reconnected, resuming processing...');
      
      if (!processingStarted) {
        socket.emit('join_session', { session_id: sessionId });
      }
    });
    
    socket.on('reconnect_attempt', (attemptNumber) => {
      console.log('WebSocket reconnection attempt:', attemptNumber);
      setConnectionStatus('connecting');
      setConnectionMessage(`Reconnection attempt ${attemptNumber}/5`);
      setProcessingStep(`Reconnection attempt ${attemptNumber}/5...`);
    });
    
    socket.on('reconnect_failed', () => {
      console.log('WebSocket reconnection failed');
      setConnectionStatus('error');
      setConnectionMessage('Reconnection failed, falling back to polling');
      setProcessingStep('Reconnection failed, using polling fallback...');
      
      // Start fallback polling
      startPollingFallback(sessionId);
    });
  };

  const stopProcessing = async () => {
    if (!currentSessionId) return;
    
    try {
      await axios.post(`${COLLAB_URL}/api/stop`, {
        session_id: currentSessionId
      });
      setProcessingStep('Stopping processing...');
    } catch (error) {
      console.error('Failed to stop processing:', error);
    }
  };

  const clearProcessingData = () => {
    localStorage.removeItem('isProcessing');
    localStorage.removeItem('processingStep');
    localStorage.removeItem('processingDetails');
    localStorage.removeItem('processingError');
    localStorage.removeItem('processingSuccess');
    localStorage.removeItem('processingComplete');
  };

  return (
    <div className="ingestion-interface">
      <div className="ingestion-sidebar">
        <h3>Document Sources ({sources.length})</h3>
        
        {sources.length > 0 ? (
          <div className="sources-list">
            {sources.map(source => (
              <div key={source.id} className={`source-item priority-${source.priority || 'medium'}`}>
                <div className="source-info">
                  <span className="source-type">{source.type.toUpperCase()}</span>
                  <div className="source-details">
                    <span className="source-path" title={source.path}>
                      {source.type === 'web' ? new URL(source.path).hostname : source.path}
                    </span>
                    {(source.priority || source.category || source.tags?.length > 0) && (
                      <div className="source-metadata">
                        {source.priority && <span className="metadata-tag">{source.priority}</span>}
                        {source.category && <span className="metadata-tag">{source.category}</span>}
                        {source.tags?.length > 0 && (
                          source.tags.slice(0,2).map((tag, i) => (
                            <span key={i} className="metadata-tag">{tag}</span>
                          ))
                        )}
                        {source.tags?.length > 2 && (
                          <span className="metadata-tag more-tags" title={`Additional tags: ${source.tags.slice(2).join(', ')}`}>+{source.tags.length - 2}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <button 
                  onClick={() => removeSource(source.id)}
                  disabled={isProcessing}
                  className="remove-source"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            <button 
              onClick={clearSources}
              disabled={isProcessing}
              className="clear-sources"
            >
              Clear All
            </button>
          </div>
        ) : (
          <p className="no-sources">No sources added yet</p>
        )}
      </div>

      <div className="ingestion-main">
        {isProcessing || processingComplete ? (
          <>
            <ProcessingStatus 
              step={processingStep}
              details={processingDetails}
              error={error}
              success={success}
              isProcessing={isProcessing}
              connectionStatus={connectionStatus}
              connectionMessage={connectionMessage}
            />
            <div className="processing-actions">
              {isProcessing && (
                <>
                  <button 
                    onClick={stopProcessing}
                    className="stop-processing"
                  >
                    Stop Processing
                  </button>
                  <button 
                    onClick={() => {
                      setIsProcessing(false);
                      setProcessingComplete(true);
                      setError('Processing force stopped');
                      setProcessingStep('Force stopped');
                      setCurrentSessionId(null);
                      clearProcessingData();
                    }}
                    className="force-reset"
                    title="Force reset if processing is stuck"
                  >
                    Force Reset
                  </button>
                </>
              )}
              {processingComplete && (
                <>
                  <button 
                    onClick={() => {
                      setProcessingComplete(false);
                      setSuccess(false);
                      setError(null);
                      setProcessingStep('');
                      setProcessingDetails([]);
                      setCurrentSessionId(null);
                      setIsProcessing(false);
                      clearProcessingData();
                    }}
                    className="back-to-ingestion"
                  >
                    ← Back to Ingestion
                  </button>
                  <button 
                    onClick={() => {
                      setSources([]);
                      setProcessingComplete(false);
                      setSuccess(false);
                      setProcessingStep('');
                      setProcessingDetails([]);
                      setCurrentSessionId(null);
                      setIsProcessing(false);
                      localStorage.removeItem('ingestionSources');
                      clearProcessingData();
                    }}
                    className="clear-and-continue"
                  >
                    {success ? 'Clear Sources & Add More' : 'Clear Sources & Retry'}
                  </button>
                </>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="ingestion-tabs">
              <button 
                className={activeTab === 'web' ? 'active' : ''}
                onClick={() => {
                  setActiveTab('web');
                  localStorage.setItem('activeTab', 'web');
                }}
              >
                <Globe size={16} /> Web
              </button>
              <button 
                className={activeTab === 'github' ? 'active' : ''}
                onClick={() => {
                  setActiveTab('github');
                  localStorage.setItem('activeTab', 'github');
                }}
              >
                <Github size={16} /> GitHub
              </button>
              <button 
                className={activeTab === 'files' ? 'active' : ''}
                onClick={() => {
                  setActiveTab('files');
                  localStorage.setItem('activeTab', 'files');
                }}
              >
                <Upload size={16} /> Files
              </button>

            </div>

            <div className="tab-content">
              {activeTab === 'web' && <WebTab addSource={addSource} />}
              {activeTab === 'github' && <GitHubTab addSource={addSource} />}
              {activeTab === 'files' && <FilesTab addSource={addSource} collabUrl={COLLAB_URL} />}

            </div>

            <div className="process-section">
              <button 
                onClick={processDocuments}
                disabled={sources.length === 0}
                className="process-button"
              >
                <Play size={16} /> Start Processing ({sources.length} sources)
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const ProcessingStatus = ({ step, details, error, success, isProcessing, connectionStatus, connectionMessage }) => {
  const logContainerRef = React.useRef(null);
  
  // Auto-scroll to bottom when new logs are added
  React.useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [details]);

  return (
    <div className="processing-status">
      <div className="status-header">
        {isProcessing && <div className="spinner"></div>}
        {error && <XCircle className="status-icon error" size={24} />}
        {success && <CheckCircle className="status-icon success" size={24} />}
        <h2>{isProcessing ? 'Processing Documents' : success ? 'Processing Complete' : 'Processing Failed'}</h2>
      </div>
      
      {/* Connection Status Indicator */}
      {connectionStatus && (
        <div className={`connection-status ${connectionStatus}`}>
          <div className="connection-indicator">
            {connectionStatus === 'connected' && <CheckCircle size={16} className="status-icon success" />}
            {connectionStatus === 'connecting' && <div className="spinner-small"></div>}
            {connectionStatus === 'error' && <XCircle size={16} className="status-icon error" />}
            {connectionStatus === 'disconnected' && <AlertCircle size={16} className="status-icon warning" />}
            <span>WebSocket: {connectionStatus}</span>
          </div>
          {connectionMessage && <span className="connection-message">{connectionMessage}</span>}
        </div>
      )}
      
      {/* Current Step Display */}
      <div className={`current-step ${error ? 'error' : success ? 'success' : ''}`}>{step}</div>
      
      {/* Processing Logs Display */}
      {details.length > 0 && (
        <div className="logs-container">
          <div className="logs-header">
            <h4>Processing Logs</h4>
          </div>
          <div 
            ref={logContainerRef}
            className="logs-content"
          >
            {details.map((detail, index) => (
              <div key={index} className="log-line">
                {detail}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {error && (
        <div className="error-message">
          <AlertCircle size={16} />
          <span>Please check your configuration and try again.</span>
        </div>
      )}
    </div>
  );
};

const WebTab = ({ addSource }) => {
  const [urls, setUrls] = useState('');
  const [docType, setDocType] = useState('web_documentation');
  const [pendingSources, setPendingSources] = useState([]);
  const [addError, setAddError] = useState('');
  const [bulkTags, setBulkTags] = useState('');

  const handlePreview = () => {
    setAddError('');
    const urlList = urls.split('\n').filter(url => url.trim());
    
    if (urlList.length === 0) {
      setAddError('Please enter at least one URL');
      return;
    }
    
    // Validate URLs
    const invalidUrls = urlList.filter(url => !url.match(/^https?:\/\/.+/));
    if (invalidUrls.length > 0) {
      setAddError('Invalid URLs found');
      return;
    }
    
    const newPending = urlList.map((url, index) => ({
      id: Date.now() + index,
      url: url.trim(),
      name: url.split('/').pop() || url,
      priority: 'medium',
      category: 'general',
      tags: ''
    }));
    
    setPendingSources(prev => [...prev, ...newPending]);
    setUrls('');
  };
  
  const updatePendingSource = (id, field, value) => {
    setPendingSources(prev => prev.map(source => 
      source.id === id ? { ...source, [field]: value } : source
    ));
  };
  
  const removePendingSource = (id) => {
    setPendingSources(prev => prev.filter(source => source.id !== id));
  };
  
  const addPendingSources = () => {
    pendingSources.forEach((source, index) => {
      let combinedTags = source.tags;
      if (bulkTags.trim()) {
        if (combinedTags.trim()) {
          combinedTags = combinedTags.endsWith(',') ? combinedTags + bulkTags : combinedTags + ',' + bulkTags;
        } else {
          combinedTags = bulkTags;
        }
      }
      const tags = combinedTags.split(',').map(tag => tag.trim()).filter(Boolean);
      addSource({
        type: 'web',
        name: `${source.name} (${index + 1})`,
        path: source.url,
        docType: docType || 'web_documentation',
        priority: source.priority,
        category: source.category,
        tags: tags,
        customMetadata: {
          source_priority: source.priority,
          document_category: source.category,
          document_tags: tags,
          ingestion_date: new Date().toISOString()
        }
      });
    });
    setPendingSources([]);
  };

  return (
    <div className="web-tab">
      <h3>Web Documents</h3>
      {addError && (
        <div className="error-message">
          <AlertCircle size={16} />
          <span>{addError}</span>
        </div>
      )}
      <textarea
        value={urls}
        onChange={(e) => setUrls(e.target.value)}
        placeholder="Enter URLs (one per line)&#10;https://docs.aws.amazon.com/vpc/latest/userguide/&#10;https://docs.aws.amazon.com/ec2/latest/userguide/&#10;https://kubernetes.io/docs/concepts/"
        rows={6}
      />
      <input
        type="text"
        value={docType}
        onChange={(e) => setDocType(e.target.value)}
        placeholder="Document type (e.g., web_documentation, api_docs)"
      />
      <button onClick={handlePreview} disabled={!urls.trim()}>
        Preview Sources ({urls.split('\n').filter(url => url.trim()).length} URLs)
      </button>
      
      {pendingSources.length > 0 && (
        <div className="pending-sources">
          <h4>Set Metadata for Web Sources:</h4>
          <div style={{padding: '10px', backgroundColor: '#f5f5f5', borderRadius: '5px', marginBottom: '15px'}}>
            <h5 style={{margin: '0 0 10px 0', color: '#333'}}>Apply to All Sources:</h5>
            <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
              <select 
                key={`web-priority-${Date.now()}`}
                onChange={(e) => {
                  if (e.target.value) {
                    setPendingSources(prev => prev.map(source => ({...source, priority: e.target.value})));
                  }
                }}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd'}}
              >
                <option value="">Set Priority for All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select 
                key={`web-category-${Date.now()}`}
                onChange={(e) => {
                  if (e.target.value) {
                    setPendingSources(prev => prev.map(source => ({...source, category: e.target.value})));
                  }
                }}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd'}}
              >
                <option value="">Set Category for All</option>
                <option value="general">General</option>
                <option value="aws-docs">AWS Docs</option>
                <option value="terraform">Terraform</option>
                <option value="pricing">Pricing</option>
              </select>
              <input
                type="text"
                placeholder="Common tags for all (comma-separated)"
                value={bulkTags}
                onChange={(e) => setBulkTags(e.target.value)}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd', minWidth: '200px'}}
              />
            </div>
          </div>
          {pendingSources.map(source => (
            <div key={source.id} className="pending-source">
              <div className="source-info">
                <div className="source-url-display">
                  <span className="source-domain">{new URL(source.url).hostname}</span>
                  <span className="source-path">{new URL(source.url).pathname}</span>
                </div>
                <span className="source-type">WEB</span>
              </div>
              <div className="source-metadata">
                <select 
                  value={source.priority} 
                  onChange={(e) => updatePendingSource(source.id, 'priority', e.target.value)}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select 
                  value={source.category} 
                  onChange={(e) => updatePendingSource(source.id, 'category', e.target.value)}
                >
                  <option value="general">General</option>
                  <option value="aws-docs">AWS Docs</option>
                  <option value="terraform">Terraform</option>
                  <option value="pricing">Pricing</option>
                  <option value="api-docs">API Docs</option>
                  <option value="tutorials">Tutorials</option>
                </select>
                <input
                  type="text"
                  value={source.tags}
                  onChange={(e) => updatePendingSource(source.id, 'tags', e.target.value)}
                  placeholder="Tags (comma-separated)"
                />
                <button onClick={() => removePendingSource(source.id)} className="remove-source">✕</button>
              </div>
            </div>
          ))}
          <button onClick={addPendingSources} className="add-pending-sources">
            Add {pendingSources.length} Web Sources
          </button>
        </div>
      )}
    </div>
  );
};

const GitHubTab = ({ addSource }) => {
  const [repos, setRepos] = useState('');
  const [token, setToken] = useState('');
  const [extensions, setExtensions] = useState('.py,.js,.ts,.md,.yml,.yaml,.json');
  const [pendingSources, setPendingSources] = useState([]);
  const [addError, setAddError] = useState('');
  const [bulkTags, setBulkTags] = useState('');

  const handlePreview = () => {
    setAddError('');
    const repoList = repos.split('\n').filter(repo => repo.trim());
    
    if (repoList.length === 0) {
      setAddError('Please enter at least one repository');
      return;
    }
    
    // Validate repo format
    const invalidRepos = repoList.filter(repo => !repo.match(/^[\w.-]+\/[\w.-]+$/));
    if (invalidRepos.length > 0) {
      setAddError('Invalid repository format. Use format: owner/repo');
      return;
    }
    
    const newPending = repoList.map((repo, index) => ({
      id: Date.now() + index,
      repo: repo.trim(),
      name: repo,
      priority: 'medium',
      category: 'code',
      tags: ''
    }));
    
    setPendingSources(prev => [...prev, ...newPending]);
    setRepos('');
  };
  
  const updatePendingSource = (id, field, value) => {
    setPendingSources(prev => prev.map(source => 
      source.id === id ? { ...source, [field]: value } : source
    ));
  };
  
  const removePendingSource = (id) => {
    setPendingSources(prev => prev.filter(source => source.id !== id));
  };
  
  const addPendingSources = () => {
    pendingSources.forEach((source, index) => {
      let combinedTags = source.tags;
      if (bulkTags.trim()) {
        if (combinedTags.trim()) {
          combinedTags = combinedTags.endsWith(',') ? combinedTags + bulkTags : combinedTags + ',' + bulkTags;
        } else {
          combinedTags = bulkTags;
        }
      }
      const tags = combinedTags.split(',').map(tag => tag.trim()).filter(Boolean);
      addSource({
        type: 'github',
        name: `${source.name} (${index + 1})`,
        path: source.repo,
        token: token || null,
        extensions: extensions ? extensions.split(',').map(ext => ext.trim()).filter(Boolean) : [],
        priority: source.priority,
        category: source.category,
        tags: tags,
        customMetadata: {
          source_priority: source.priority,
          document_category: source.category,
          document_tags: tags,
          repository_type: 'github',
          ingestion_date: new Date().toISOString()
        }
      });
    });
    setPendingSources([]);
  };

  return (
    <div className="github-tab">
      <h3>GitHub Repositories</h3>
      {addError && (
        <div className="error-message">
          <AlertCircle size={16} />
          <span>{addError}</span>
        </div>
      )}
      <textarea
        value={repos}
        onChange={(e) => setRepos(e.target.value)}
        placeholder="Enter repositories (one per line)&#10;owner/repo&#10;aws/aws-cli&#10;kubernetes/kubernetes"
        rows={4}
      />
      <input
        type="password"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        placeholder="GitHub token (optional for public repos)"
      />
      <input
        type="text"
        value={extensions}
        onChange={(e) => setExtensions(e.target.value)}
        placeholder="File extensions (e.g., .py,.js,.md)"
      />
      <button onClick={handlePreview} disabled={!repos.trim()}>
        Preview Sources ({repos.split('\n').filter(repo => repo.trim()).length} repos)
      </button>
      
      {pendingSources.length > 0 && (
        <div className="pending-sources">
          <h4>Set Metadata for GitHub Sources:</h4>
          <div style={{padding: '10px', backgroundColor: '#f5f5f5', borderRadius: '5px', marginBottom: '15px'}}>
            <h5 style={{margin: '0 0 10px 0', color: '#333'}}>Apply to All Sources:</h5>
            <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
              <select 
                key={`github-priority-${Date.now()}`}
                onChange={(e) => {
                  if (e.target.value) {
                    setPendingSources(prev => prev.map(source => ({...source, priority: e.target.value})));
                  }
                }}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd'}}
              >
                <option value="">Set Priority for All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select 
                key={`github-category-${Date.now()}`}
                onChange={(e) => {
                  if (e.target.value) {
                    setPendingSources(prev => prev.map(source => ({...source, category: e.target.value})));
                  }
                }}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd'}}
              >
                <option value="">Set Category for All</option>
                <option value="general">General</option>
                <option value="aws-docs">AWS Docs</option>
                <option value="terraform">Terraform</option>
                <option value="pricing">Pricing</option>
              </select>
              <input
                type="text"
                placeholder="Common tags for all (comma-separated)"
                value={bulkTags}
                onChange={(e) => setBulkTags(e.target.value)}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd', minWidth: '200px'}}
              />
            </div>
          </div>
          {pendingSources.map(source => (
            <div key={source.id} className="pending-source">
              <div className="source-info">
                <span className="source-name">{source.repo}</span>
                <span className="source-type">GITHUB</span>
              </div>
              <div className="source-metadata">
                <select 
                  value={source.priority} 
                  onChange={(e) => updatePendingSource(source.id, 'priority', e.target.value)}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select 
                  value={source.category} 
                  onChange={(e) => updatePendingSource(source.id, 'category', e.target.value)}
                >
                  <option value="general">General</option>
                  <option value="aws-docs">AWS Docs</option>
                  <option value="terraform">Terraform</option>
                  <option value="pricing">Pricing</option>
                  <option value="api-docs">API Docs</option>
                  <option value="tutorials">Tutorials</option>
                </select>
                <input
                  type="text"
                  value={source.tags}
                  onChange={(e) => updatePendingSource(source.id, 'tags', e.target.value)}
                  placeholder="Tags (comma-separated)"
                />
                <button onClick={() => removePendingSource(source.id)} className="remove-source">✕</button>
              </div>
            </div>
          ))}
          <button onClick={addPendingSources} className="add-pending-sources">
            Add {pendingSources.length} GitHub Sources
          </button>
        </div>
      )}
    </div>
  );
};

const FilesTab = ({ addSource, collabUrl }) => {
  const [uploading, setUploading] = useState(false);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [filePaths, setFilePaths] = useState('');
  const [docType, setDocType] = useState('');
  const [addError, setAddError] = useState('');
  const [bulkTags, setBulkTags] = useState('');
  
  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    setAddError('');
    const newPendingFiles = [];
    const failedUploads = [];
    
    for (let i = 0; i < acceptedFiles.length; i++) {
      const file = acceptedFiles[i];
      
      try {
        console.log('Uploading file:', file.name, 'Size:', file.size, 'Type:', file.type);
        
        const formData = new FormData();
        formData.append('file', file);
        
        const uploadResponse = await axios.post(`${collabUrl}/api/upload`, formData, {
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            console.log(`Upload progress for ${file.name}: ${percentCompleted}%`);
          }
        });
        
        if (uploadResponse.data.status === 'success') {
          newPendingFiles.push({
            id: Date.now() + i,
            name: file.name,
            path: uploadResponse.data.filepath,
            type: file.type.includes('pdf') ? 'pdf' : 'csv',
            priority: 'medium',
            category: '',
            tags: '',
            uploaded: true
          });
        } else {
          failedUploads.push(file.name);
        }
      } catch (error) {
        console.error('Upload failed for', file.name, error);
        if (error.code === 'ECONNABORTED') {
          failedUploads.push(`${file.name} (timeout)`);
        } else {
          failedUploads.push(`${file.name} (${error.message})`);
        }
      }
    }
    
    if (failedUploads.length > 0) {
      setAddError(`Failed to upload: ${failedUploads.join(', ')}`);
    }
    
    setPendingFiles(prev => [...prev, ...newPendingFiles]);
    setUploading(false);
  }, [collabUrl]);

  const handlePreview = () => {
    setAddError('');
    const pathList = filePaths.split('\n').filter(path => path.trim());
    
    if (pathList.length === 0) {
      setAddError('Please enter at least one file path');
      return;
    }
    
    const newPending = pathList.map((filePath, index) => {
      const fileName = filePath.split('/').pop();
      const fileType = fileName.split('.').pop().toLowerCase();
      
      return {
        id: Date.now() + index + 1000,
        path: filePath.trim(),
        name: fileName,
        type: fileType === 'pdf' ? 'pdf' : 'csv',
        priority: 'medium',
        category: 'document',
        tags: '',
        uploaded: false
      };
    });
    
    setPendingFiles(prev => [...prev, ...newPending]);
    setFilePaths('');
  };
  
  const updatePendingFile = (id, field, value) => {
    setPendingFiles(prev => prev.map(file => 
      file.id === id ? { ...file, [field]: value } : file
    ));
  };
  
  const removePendingFile = (id) => {
    setPendingFiles(prev => prev.filter(file => file.id !== id));
  };
  
  const addPendingFiles = () => {
    pendingFiles.forEach((file, index) => {
      let combinedTags = file.tags;
      if (bulkTags.trim()) {
        if (combinedTags.trim()) {
          combinedTags = combinedTags.endsWith(',') ? combinedTags + bulkTags : combinedTags + ',' + bulkTags;
        } else {
          combinedTags = bulkTags;
        }
      }
      const tags = combinedTags.split(',').map(tag => tag.trim()).filter(Boolean);
      addSource({
        type: file.type,
        name: file.name,
        path: file.path,
        docType: docType || `${file.type}_document`,
        priority: file.priority,
        category: file.category || 'document',
        tags: tags,
        uploaded: file.uploaded,
        customMetadata: {
          source_priority: file.priority,
          document_category: file.category || 'document',
          document_tags: tags,
          file_type: file.type,
          ingestion_date: new Date().toISOString()
        }
      });
    });
    setPendingFiles([]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/csv': ['.csv'],
      'text/plain': ['.csv']
    },
    disabled: uploading,
    multiple: true
  });

  return (
    <div className="files-tab">
      <h3>File Upload</h3>
      {addError && (
        <div className="error-message">
          <AlertCircle size={16} />
          <span>{addError}</span>
        </div>
      )}
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${uploading ? 'uploading' : ''}`}>
        <input {...getInputProps()} />
        <FileText size={48} />
        {uploading ? (
          <p>Uploading files...</p>
        ) : isDragActive ? (
          <p>Drop files here...</p>
        ) : (
          <p>Drag & drop PDF or CSV files here, or click to browse</p>
        )}
      </div>
      
      <div className="file-path-section">
        <h4>Or enter file paths for large files:</h4>
        {addError && (
          <div className="error-message">
            <AlertCircle size={16} />
            <span>{addError}</span>
          </div>
        )}
        <textarea
          value={filePaths}
          onChange={(e) => setFilePaths(e.target.value)}
          placeholder="Enter file paths (one per line)&#10;/workspace/data/large_file.csv&#10;/workspace/docs/manual.pdf"
          rows={3}
        />
        <input
          type="text"
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          placeholder="Document type (optional)"
        />
        <button onClick={handlePreview} disabled={!filePaths.trim()}>
          Preview Files ({filePaths.split('\n').filter(path => path.trim()).length})
        </button>
      </div>
      
      {pendingFiles.length > 0 && (
        <div className="pending-files">
          <h4>Set Metadata for Files:</h4>
          <div style={{padding: '10px', backgroundColor: '#f5f5f5', borderRadius: '5px', marginBottom: '15px'}}>
            <h5 style={{margin: '0 0 10px 0', color: '#333'}}>Apply to All Files:</h5>
            <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
              <select 
                key={`files-priority-${Date.now()}`}
                onChange={(e) => {
                  if (e.target.value) {
                    setPendingFiles(prev => prev.map(file => ({...file, priority: e.target.value})));
                  }
                }}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd'}}
              >
                <option value="">Set Priority for All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select 
                key={`files-category-${Date.now()}`}
                onChange={(e) => {
                  if (e.target.value) {
                    setPendingFiles(prev => prev.map(file => ({...file, category: e.target.value})));
                  }
                }}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd'}}
              >
                <option value="">Set Category for All</option>
                <option value="general">General</option>
                <option value="aws-docs">AWS Docs</option>
                <option value="terraform">Terraform</option>
                <option value="pricing">Pricing</option>
              </select>
              <input
                type="text"
                placeholder="Common tags for all (comma-separated)"
                value={bulkTags}
                onChange={(e) => setBulkTags(e.target.value)}
                style={{padding: '5px', borderRadius: '3px', border: '1px solid #ddd', minWidth: '200px'}}
              />
            </div>
          </div>
          {pendingFiles.map(file => (
            <div key={file.id} className="pending-file">
              <div className="file-info">
                <span className="file-name">{file.uploaded ? file.name : file.path}</span>
                <span className="file-type">{file.type.toUpperCase()}</span>
              </div>
              <div className="file-metadata">
                <select 
                  value={file.priority} 
                  onChange={(e) => updatePendingFile(file.id, 'priority', e.target.value)}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select 
                  value={file.category} 
                  onChange={(e) => updatePendingFile(file.id, 'category', e.target.value)}
                >
                  <option value="general">General</option>
                  <option value="aws-docs">AWS Docs</option>
                  <option value="terraform">Terraform</option>
                  <option value="pricing">Pricing</option>
                  <option value="api-docs">API Docs</option>
                  <option value="tutorials">Tutorials</option>
                </select>
                <input
                  type="text"
                  value={file.tags}
                  onChange={(e) => updatePendingFile(file.id, 'tags', e.target.value)}
                  placeholder="Tags (comma-separated)"
                />
                <button onClick={() => removePendingFile(file.id)} className="remove-file">✕</button>
              </div>
            </div>
          ))}
          <button onClick={addPendingFiles} className="add-pending-files">
            Add {pendingFiles.length} Files to Sources
          </button>
        </div>
      )}
    </div>
  );
};





export default IngestionInterface;