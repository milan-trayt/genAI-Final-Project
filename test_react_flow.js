const io = require('socket.io-client');
const axios = require('axios');

async function testReactFrontendFlow() {
  const sessionId = `session_${Date.now()}`;
  console.log('🧪 Testing React frontend websocket flow with session:', sessionId);
  
  const socket = io('http://localhost:8503', {
    transports: ['polling', 'websocket'],
    timeout: 20000,
    pingTimeout: 60000,
    pingInterval: 25000,
    reconnection: true,
    reconnectionAttempts: 3,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    forceNew: true,
    autoConnect: true,
    upgrade: true,
    rememberUpgrade: true
  });
  
  let processingStarted = false;
  let updateCount = 0;
  
  socket.on('connect', () => {
    console.log('✅ WebSocket connected');
    console.log('🔧 Connected, joining room...');
    socket.emit('join_session', { session_id: sessionId });
    
    // Set a timeout to disconnect if no response
    setTimeout(() => {
      if (!processingStarted) {
        console.log('❌ Connection timeout - no response from server');
        socket.disconnect();
        process.exit(1);
      }
    }, 10000);
  });
  
  socket.on('joined', async (data) => {
    console.log('✅ Joined room:', data.session_id);
    if (processingStarted) return;
    processingStarted = true;
    
    console.log('🔧 Starting processing...');
    
    await new Promise(resolve => setTimeout(resolve, 500));
    
    try {
      const processingSources = [{
        type: 'web',
        name: 'Test Web Source',
        path: 'https://httpbin.org/json',
        docType: 'test_document'
      }];
      
      const inputData = JSON.stringify({
        sources: processingSources,
        batch_size: 1
      });
      
      await axios.post('http://localhost:8503/api/process', {
        input: inputData,
        session_id: sessionId
      });
      
      console.log('✅ Processing request sent successfully');
      
    } catch (error) {
      console.error('❌ Failed to start processing:', error.message);
      socket.disconnect();
      process.exit(1);
    }
  });
  
  socket.on('processing_update', (data) => {
    updateCount++;
    console.log(`📡 Update #${updateCount} [${data.type}]: ${data.message}`);
    
    if (data.type === 'complete') {
      if (data.status === 'success') {
        console.log('🎉 Processing completed successfully!');
        if (data.data?.stats) {
          const stats = data.data.stats;
          console.log(`📊 Final Statistics:`);
          console.log(`   • Total sources: ${stats.total_sources}`);
          console.log(`   • Processing time: ${stats.processing_time?.toFixed(2)}s`);
        }
      } else {
        console.log('❌ Processing failed:', data.message);
      }
      socket.disconnect();
      process.exit(0);
    } else if (data.type === 'error') {
      console.log('❌ Processing error:', data.message);
      socket.disconnect();
      process.exit(1);
    }
  });
  
  socket.on('connect_error', (error) => {
    console.error('❌ WebSocket connection failed:', error.message);
    process.exit(1);
  });
  
  socket.on('disconnect', (reason) => {
    console.log('🔌 WebSocket disconnected:', reason);
  });
  
  // Timeout after 60 seconds
  setTimeout(() => {
    console.log(`⏰ Test timeout - received ${updateCount} updates`);
    socket.disconnect();
    process.exit(updateCount > 0 ? 0 : 1);
  }, 60000);
}

testReactFrontendFlow();