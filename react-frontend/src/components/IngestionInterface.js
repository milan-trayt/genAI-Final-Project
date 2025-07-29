import React, { useState, useCallback } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Github, Globe, Trash2, Play, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import io from 'socket.io-client';

const IngestionInterface = () => {
  const [sources, setSources] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState('');
  const [processingDetails, setProcessingDetails] = useState([]);
  const [activeTab, setActiveTab] = useState('web');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [processingComplete, setProcessingComplete] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [connectionMessage, setConnectionMessage] = useState('');

  const COLLAB_URL = process.env.REACT_APP_COLLAB_URL || 'http://localhost:8503';


  const addSource = (source) => {
    setSources(prevSources => [...prevSources, { ...source, id: Date.now() + Math.random() }]);
  };

  const removeSource = (id) => {
    setSources(sources.filter(s => s.id !== id));
  };

  const clearSources = () => {
    setSources([]);
  };

  const startPollingFallback = async (sessionId) => {
    let pollCount = 0;
    const maxPolls = 60; // Poll for up to 5 minutes (60 * 5s intervals)
    
    setProcessingDetails(prev => [...prev, '🔄 WebSocket failed, switching to polling mode...']);
    
    const poll = async () => {
      try {
        // Check if processing is still active by trying to get status
        const response = await axios.get(`${COLLAB_URL}/api/status`);
        
        if (response.data.status === 'ready') {
          setProcessingDetails(prev => [...prev, `🔄 Polling for status updates... (${pollCount + 1}/${maxPolls})`]);
          
          pollCount++;
          if (pollCount < maxPolls && isProcessing) {
            setTimeout(poll, 5000); // Poll every 5 seconds
          } else if (pollCount >= maxPolls) {
            setError('Processing timeout - no updates received after 5 minutes');
            setProcessingStep('❌ Processing timeout');
            setIsProcessing(false);
            setProcessingComplete(true);
          }
        } else {
          // Processing might be complete, check one more time
          setProcessingDetails(prev => [...prev, '✅ Processing appears to be complete']);
          setSuccess(true);
          setProcessingStep('🎉 Processing completed (detected via polling)');
          setIsProcessing(false);
          setProcessingComplete(true);
        }
      } catch (error) {
        setError('Failed to connect to processing server');
        setProcessingStep('❌ Connection failed');
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
    setProcessingStep('🔧 Connecting to WebSocket...');
    setError(null);
    setSuccess(false);
    setProcessingComplete(false);
    
    const sessionId = `session_${Date.now()}`;
    
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
      setProcessingStep('🔧 Connected, joining room...');
      socket.emit('join_session', { session_id: sessionId });
      
      // Set a timeout to disconnect if no response
      setTimeout(() => {
        if (!processingStarted) {
          console.log('No response received, disconnecting');
          setConnectionStatus('error');
          setConnectionMessage('Connection timeout - no response from server');
          setProcessingStep('❌ Connection timeout');
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
      
      setProcessingStep('🔧 Starting processing...');
      
      await new Promise(resolve => setTimeout(resolve, 500));
      
      try {
        const processingSources = sources.map(source => ({
          type: source.type,
          name: source.name,
          path: source.path,
          docType: source.docType || 'document',
          token: source.token,
          extensions: source.extensions,
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
        setProcessingStep('❌ Connection failed');
        setProcessingDetails(prev => [...prev, `Error: ${errorMessage}`]);
        setError(errorMessage);
        socket.disconnect();
      }
    });
    
    socket.on('processing_update', (data) => {
      console.log('🎯 RECEIVED processing_update:', data);
      
      if (data.type === 'log') {
        setProcessingDetails(prev => [...prev, data.message]);
        setProcessingStep(data.message);
      } else if (data.type === 'progress') {
        setProcessingDetails(prev => [...prev, data.message]);
        setProcessingStep(data.message);
        // Could add progress bar here if needed
      } else if (data.type === 'complete') {
        // Only mark as complete if this is the final completion (all sources processed)
        if (data.final === true || data.all_complete === true) {
          setIsProcessing(false);
          setProcessingComplete(true);
          if (data.status === 'success') {
            setSuccess(true);
            setProcessingStep('🎉 Processing completed successfully!');
            // Add final stats if available
            if (data.data?.stats) {
              const stats = data.data.stats;
              setProcessingDetails(prev => [...prev, 
                `📊 Final Statistics:`,
                `   • Total sources: ${stats.total_sources}`,
                `   • Processing time: ${stats.processing_time?.toFixed(2)}s`
              ]);
            }
          } else {
            setError(data.message || 'Processing failed');
            setProcessingStep('❌ Processing failed');
          }
          socket.disconnect();
        } else {
          // Individual source completed, just log it
          setProcessingDetails(prev => [...prev, data.message || '✅ Source completed']);
          if (data.message) {
            setProcessingStep(data.message);
          }
        }
      } else if (data.type === 'error') {
        setIsProcessing(false);
        setProcessingComplete(true);
        setError(data.message || 'Processing error occurred');
        setProcessingStep('❌ Processing failed');
        if (data.details) {
          setProcessingDetails(prev => [...prev, `Error details: ${data.details}`]);
        }
        socket.disconnect();
      }
    });
    
    socket.on('connect_error', (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
      setConnectionMessage('WebSocket connection failed, falling back to polling');
      setProcessingStep('🔄 WebSocket failed, using polling fallback...');
      
      // Start fallback polling
      startPollingFallback(sessionId);
    });
    
    socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setConnectionStatus('disconnected');
      setConnectionMessage(`Disconnected: ${reason}`);
      
      if (reason === 'ping timeout' && !processingComplete) {
        setProcessingStep('🔄 Connection lost, attempting to reconnect...');
      }
    });
    
    socket.on('reconnect', (attemptNumber) => {
      console.log('WebSocket reconnected after', attemptNumber, 'attempts');
      setConnectionStatus('connected');
      setConnectionMessage('Reconnected to processing server');
      setProcessingStep('🔄 Reconnected, resuming processing...');
      
      if (!processingStarted) {
        socket.emit('join_session', { session_id: sessionId });
      }
    });
    
    socket.on('reconnect_attempt', (attemptNumber) => {
      console.log('WebSocket reconnection attempt:', attemptNumber);
      setConnectionStatus('connecting');
      setConnectionMessage(`Reconnection attempt ${attemptNumber}/5`);
      setProcessingStep(`🔄 Reconnection attempt ${attemptNumber}/5...`);
    });
    
    socket.on('reconnect_failed', () => {
      console.log('WebSocket reconnection failed');
      setConnectionStatus('error');
      setConnectionMessage('Reconnection failed, falling back to polling');
      setProcessingStep('❌ Reconnection failed, using polling fallback...');
      
      // Start fallback polling
      startPollingFallback(sessionId);
    });
  };

  return (
    <div className="ingestion-interface">
      <div className="ingestion-sidebar">
        <h3>📚 Document Sources ({sources.length})</h3>
        
        {sources.length > 0 ? (
          <div className="sources-list">
            {sources.map(source => (
              <div key={source.id} className="source-item">
                <div className="source-info">
                  <span className="source-type">{source.type.toUpperCase()}</span>
                  <span className="source-name">{source.name}</span>
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
              🗑️ Clear All
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
            {processingComplete && (
              <div className="processing-actions">
                <button 
                  onClick={() => {
                    setProcessingComplete(false);
                    setSuccess(false);
                    setError(null);
                    setProcessingStep('');
                    setProcessingDetails([]);
                  }}
                  className="back-to-ingestion"
                >
                  ← Back to Ingestion
                </button>
                {success && (
                  <button 
                    onClick={() => {
                      setSources([]);
                      setProcessingComplete(false);
                      setSuccess(false);
                      setProcessingStep('');
                      setProcessingDetails([]);
                    }}
                    className="clear-and-continue"
                  >
                    Clear Sources & Continue
                  </button>
                )}
              </div>
            )}
          </>
        ) : (
          <>
            <div className="ingestion-tabs">
              <button 
                className={activeTab === 'web' ? 'active' : ''}
                onClick={() => setActiveTab('web')}
              >
                <Globe size={16} /> Web
              </button>
              <button 
                className={activeTab === 'github' ? 'active' : ''}
                onClick={() => setActiveTab('github')}
              >
                <Github size={16} /> GitHub
              </button>
              <button 
                className={activeTab === 'files' ? 'active' : ''}
                onClick={() => setActiveTab('files')}
              >
                <Upload size={16} /> Files
              </button>

            </div>

            <div className="tab-content">
              {activeTab === 'web' && <WebTab addSource={addSource} />}
              {activeTab === 'github' && <GitHubTab addSource={addSource} />}
              {activeTab === 'files' && <FilesTab addSource={addSource} />}

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
        <h2>{isProcessing ? '🔄 Processing Documents' : success ? '✅ Processing Complete' : '❌ Processing Failed'}</h2>
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
  const [addError, setAddError] = useState('');

  const handleSubmit = () => {
    setAddError('');
    const urlList = urls.split('\n').filter(url => url.trim());
    
    if (urlList.length === 0) {
      setAddError('Please enter at least one URL');
      return;
    }
    
    // Validate URLs
    const invalidUrls = urlList.filter(url => !url.match(/^https?:\/\/.+/));
    if (invalidUrls.length > 0) {
      setAddError(`Invalid URLs: ${invalidUrls.join(', ')}`);
      return;
    }
    
    // Add each URL as a separate source with unique IDs
    urlList.forEach((url, index) => {
      setTimeout(() => {
        addSource({
          type: 'web',
          name: `${url.split('/').pop() || url} (${index + 1})`,
          path: url.trim(),
          docType: docType || 'web_documentation'
        });
      }, index * 10); // Small delay to ensure unique timestamps
    });
    
    setUrls('');
    setDocType('web_documentation');
  };

  return (
    <div className="web-tab">
      <h3>🌐 Web Documents</h3>
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
      <button onClick={handleSubmit} disabled={!urls.trim()}>
        Add Web Sources ({urls.split('\n').filter(url => url.trim()).length} URLs)
      </button>
    </div>
  );
};

const GitHubTab = ({ addSource }) => {
  const [repos, setRepos] = useState('');
  const [token, setToken] = useState('');
  const [extensions, setExtensions] = useState('.py,.js,.ts,.md,.yml,.yaml,.json');
  const [addError, setAddError] = useState('');

  const handleSubmit = () => {
    setAddError('');
    const repoList = repos.split('\n').filter(repo => repo.trim());
    
    if (repoList.length === 0) {
      setAddError('Please enter at least one repository');
      return;
    }
    
    // Validate repo format
    const invalidRepos = repoList.filter(repo => !repo.match(/^[\w.-]+\/[\w.-]+$/));
    if (invalidRepos.length > 0) {
      setAddError(`Invalid repository format: ${invalidRepos.join(', ')}. Use format: owner/repo`);
      return;
    }
    
    // Add each repo as a separate source with unique IDs
    repoList.forEach((repo, index) => {
      setTimeout(() => {
        addSource({
          type: 'github',
          name: `${repo} (${index + 1})`,
          path: repo.trim(),
          token: token || null,
          extensions: extensions ? extensions.split(',').map(ext => ext.trim()).filter(Boolean) : []
        });
      }, index * 10); // Small delay to ensure unique timestamps
    });
    
    setRepos('');
    setToken('');
  };

  return (
    <div className="github-tab">
      <h3>🐙 GitHub Repositories</h3>
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
      <button onClick={handleSubmit} disabled={!repos.trim()}>
        Add GitHub Sources ({repos.split('\n').filter(repo => repo.trim()).length} repos)
      </button>
    </div>
  );
};

const FilesTab = ({ addSource }) => {
  const [uploading, setUploading] = useState(false);
  
  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    
    for (let i = 0; i < acceptedFiles.length; i++) {
      const file = acceptedFiles[i];
      
      try {
        const formData = new FormData();
        formData.append('file', file);
        
        const uploadResponse = await axios.post(`${COLLAB_URL}/api/upload`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
        
        if (uploadResponse.data.status === 'success') {
          addSource({
            type: file.type.includes('pdf') ? 'pdf' : 'csv',
            name: `${file.name} (${i + 1})`,
            path: uploadResponse.data.filepath,
            uploaded: true
          });
        }
      } catch (error) {
        console.error('Upload error:', error);
      }
    }
    
    setUploading(false);
  }, [addSource]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/csv': ['.csv']
    }
  });

  return (
    <div className="files-tab">
      <h3>📁 File Upload</h3>
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${uploading ? 'uploading' : ''}`}>
        <input {...getInputProps()} disabled={uploading} />
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
        <FilePathInput addSource={addSource} />
      </div>
    </div>
  );
};

const FilePathInput = ({ addSource }) => {
  const [filePaths, setFilePaths] = useState('');
  const [docType, setDocType] = useState('');
  const [addError, setAddError] = useState('');

  const handleSubmit = () => {
    setAddError('');
    const pathList = filePaths.split('\n').filter(path => path.trim());
    
    if (pathList.length === 0) {
      setAddError('Please enter at least one file path');
      return;
    }
    
    // Add each file path as a separate source with unique IDs
    pathList.forEach((filePath, index) => {
      setTimeout(() => {
        const fileName = filePath.split('/').pop();
        const fileType = fileName.split('.').pop().toLowerCase();
        
        addSource({
          type: fileType === 'pdf' ? 'pdf' : 'csv',
          name: `${fileName} (${index + 1})`,
          path: filePath.trim(),
          docType: docType || `${fileType}_document`
        });
      }, index * 10); // Small delay to ensure unique timestamps
    });
    
    setFilePaths('');
    setDocType('');
  };

  return (
    <div className="file-path-input">
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
      <div className="file-path-actions">
        <input
          type="text"
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          placeholder="Document type (optional)"
        />
        <button onClick={handleSubmit} disabled={!filePaths.trim()}>
          Add from Paths ({filePaths.split('\n').filter(path => path.trim()).length} files)
        </button>
      </div>
    </div>
  );
};



export default IngestionInterface;