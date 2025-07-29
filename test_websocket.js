const io = require('socket.io-client');
const axios = require('axios');

const sessionId = `session_${Date.now()}`;
console.log('🧪 Testing websocket with session:', sessionId);

const socket = io('http://localhost:8503', {
  transports: ['polling'],  // Force polling to avoid upgrade issues
  timeout: 20000,
  reconnection: false,
  forceNew: true
});

let updateCount = 0;

// Log all events
socket.onAny((eventName, ...args) => {
  console.log(`🔔 Event: ${eventName}`, args);
});

socket.on('connect', () => {
  console.log('✅ Connected');
  socket.emit('join_session', { session_id: sessionId });
});

socket.on('joined', async (data) => {
  console.log('✅ Joined:', data.session_id);
  
  // Start processing after a delay
  setTimeout(async () => {
    try {
      const response = await axios.post('http://localhost:8503/api/process', {
        input: JSON.stringify({
          sources: [{
            type: 'web',
            name: 'Test Source',
            path: 'https://httpbin.org/json',
            docType: 'test'
          }],
          batch_size: 1
        }),
        session_id: sessionId
      });
      console.log('✅ Processing started:', response.data.status);
    } catch (error) {
      console.error('❌ Processing failed:', error.message);
    }
  }, 1000);
});

socket.on('processing_update', (data) => {
  updateCount++;
  console.log(`📡 Update #${updateCount}:`, data);
  
  if (data.type === 'complete') {
    console.log('🏁 Processing complete');
    setTimeout(() => {
      socket.disconnect();
      process.exit(0);
    }, 1000);
  }
});

socket.on('error', (error) => {
  console.error('❌ Socket error:', error);
});

socket.on('connect_error', (error) => {
  console.error('❌ Connection error:', error);
});

socket.on('disconnect', (reason) => {
  console.log('🔌 Disconnected:', reason);
});

// Timeout
setTimeout(() => {
  console.log(`⏰ Timeout - received ${updateCount} updates`);
  socket.disconnect();
  process.exit(updateCount > 0 ? 0 : 1);
}, 30000);