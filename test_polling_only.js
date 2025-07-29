#!/usr/bin/env node
/**
 * Test polling-only transport to debug client-side reception issues
 */

const io = require('socket.io-client');
const axios = require('axios');

async function testPollingOnly() {
  console.log('🧪 Testing Polling-Only Transport');
  
  const sessionId = `polling_test_${Date.now()}`;
  console.log(`📝 Session ID: ${sessionId}`);
  
  const socket = io('http://localhost:8503', {
    transports: ['polling'],  // Force polling only
    timeout: 30000,
    pingTimeout: 120000,
    pingInterval: 30000,
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    forceNew: true,
    autoConnect: true,
    upgrade: false,  // Disable upgrade to websocket
    rememberUpgrade: false,
    query: {
      session_id: sessionId  // Pass session ID in query for better tracking
    }
  });
  
  let processingStarted = false;
  let updateCount = 0;
  let testMessageReceived = false;
  
  // Log all events with timestamps
  socket.onAny((eventName, ...args) => {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] 🔔 Event [${eventName}]:`, JSON.stringify(args, null, 2));
  });
  
  socket.on('connect', () => {
    console.log('✅ WebSocket connected with polling transport');
    console.log('🔧 Connected, joining room...');
    socket.emit('join_session', { session_id: sessionId });
    
    // Set a timeout to disconnect if no response
    setTimeout(() => {
      if (!processingStarted) {
        console.log('❌ Connection timeout - no response from server');
        socket.disconnect();
        process.exit(1);
      }
    }, 15000);
  });
  
  socket.on('joined', async (data) => {
    console.log('✅ Joined room:', data.session_id);
    if (processingStarted) return;
    processingStarted = true;
    
    console.log('🔧 Starting processing...');
    
    // Wait a bit longer to ensure the connection is stable
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    try {
      const processingSources = [{
        type: 'web',
        name: 'Polling Test Source',
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
      console.log('⏳ Waiting for processing updates (polling transport)...');
      
      // Add a periodic check to see if we're still connected
      const connectionCheck = setInterval(() => {
        console.log(`🔍 Connection check - Connected: ${socket.connected}, Updates received: ${updateCount}`);
        if (!socket.connected) {
          console.log('❌ Socket disconnected during processing');
          clearInterval(connectionCheck);
        }
      }, 5000);
      
      // Clear the interval after 60 seconds
      setTimeout(() => clearInterval(connectionCheck), 60000);
      
    } catch (error) {
      console.error('❌ Failed to start processing:', error.message);
      socket.disconnect();
      process.exit(1);
    }
  });
  
  socket.on('processing_update', (data) => {
    updateCount++;
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] 📡 Update #${updateCount} [${data.type}]: ${data.message}`);
    
    // Check if this is the test message
    if (data.message && data.message.includes('Test: WebSocket connection verified')) {
      testMessageReceived = true;
      console.log('✅ Test message received successfully');
    }
    
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
      
      if (testMessageReceived && updateCount > 1) {
        console.log('🎉 SUCCESS: Both test message and processing updates received');
        process.exit(0);
      } else if (testMessageReceived) {
        console.log('⚠️  PARTIAL: Test message received but no processing updates');
        process.exit(1);
      } else {
        console.log('❌ FAILURE: No messages received at all');
        process.exit(1);
      }
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
    console.log(`📊 Final stats: ${updateCount} updates received, test message: ${testMessageReceived}`);
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
  
  // Timeout after 90 seconds
  setTimeout(() => {
    console.log(`⏰ Test timeout - received ${updateCount} updates`);
    console.log(`📊 Test message received: ${testMessageReceived}`);
    
    if (updateCount === 0) {
      console.log('❌ COMPLETE FAILURE: No updates received at all');
      process.exit(1);
    } else if (testMessageReceived && updateCount === 1) {
      console.log('⚠️  PARTIAL FAILURE: Only test message received, no processing updates');
      process.exit(1);
    } else if (updateCount > 1) {
      console.log('✅ PARTIAL SUCCESS: Some updates received');
      process.exit(0);
    }
  }, 90000);
}

// Run the test
testPollingOnly().catch(error => {
  console.error('💥 Test failed:', error.message);
  process.exit(1);
});