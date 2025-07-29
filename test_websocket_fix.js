#!/usr/bin/env node
/**
 * Comprehensive test to debug websocket processing updates
 */

const io = require('socket.io-client');
const axios = require('axios');

async function testWebSocketProcessing() {
  console.log('🧪 Comprehensive WebSocket Processing Test');
  
  const sessionId = `debug_session_${Date.now()}`;
  console.log(`📝 Session ID: ${sessionId}`);
  
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
  let connectionLost = false;
  
  // Log all events
  socket.onAny((eventName, ...args) => {
    console.log(`🔔 Event [${eventName}]:`, JSON.stringify(args, null, 2));
  });
  
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
        name: 'Debug Test Source',
        path: 'https://httpbin.org/json',
        docType: 'test_document'
      }];
      
      const inputData = JSON.stringify({
        sources: processingSources,
        batch_size: 1
      });
      
      console.log('📤 Sending processing request...');
      const response = await axios.post('http://localhost:8503/api/process', {
        input: inputData,
        session_id: sessionId
      });
      
      console.log('✅ Processing request sent:', response.data.status);
      console.log('⏳ Waiting for processing updates...');
      
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
      console.log(`✅ Test completed with ${updateCount} updates received`);
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
    if (!connectionLost && updateCount === 0) {
      connectionLost = true;
      console.log('⚠️  Disconnected before receiving any updates');
    }
  });
  
  socket.on('reconnect', (attemptNumber) => {
    console.log(`🔄 Reconnected after ${attemptNumber} attempts`);
  });
  
  socket.on('reconnect_attempt', (attemptNumber) => {
    console.log(`🔄 Reconnection attempt ${attemptNumber}`);
  });
  
  socket.on('reconnect_failed', () => {
    console.log('❌ Reconnection failed');
  });
  
  // Timeout after 60 seconds
  setTimeout(() => {
    console.log(`⏰ Test timeout - received ${updateCount} updates`);
    if (updateCount === 0) {
      console.log('❌ No processing updates received - websocket communication failed');
      process.exit(1);
    } else {
      console.log('✅ Some updates received - partial success');
      process.exit(0);
    }
  }, 60000);
}

// Run the test
testWebSocketProcessing().catch(error => {
  console.error('💥 Test failed:', error.message);
  process.exit(1);
});