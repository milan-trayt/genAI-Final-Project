#!/usr/bin/env node
/**
 * Comprehensive test for full WebSocket functionality with transport upgrades
 */

const io = require('socket.io-client');
const axios = require('axios');

async function testFullWebSocket() {
  console.log('🧪 Testing Full WebSocket with Transport Upgrades');
  
  const sessionId = `full_test_${Date.now()}`;
  console.log(`📝 Session ID: ${sessionId}`);
  
  const socket = io('http://localhost:8503', {
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
  
  let processingStarted = false;
  let updateCount = 0;
  let testMessageReceived = false;
  let transportUpgraded = false;
  let processingCompleted = false;
  
  // Track transport changes
  socket.on('connect', () => {
    console.log(`✅ Connected with transport: ${socket.io.engine.transport.name}`);
    setConnectionStatus('connected');
    
    // Monitor transport upgrades
    socket.io.engine.on('upgrade', () => {
      console.log(`🚀 Transport upgraded to: ${socket.io.engine.transport.name}`);
      transportUpgraded = true;
    });
    
    socket.io.engine.on('upgradeError', (error) => {
      console.log(`❌ Transport upgrade failed: ${error}`);
    });
    
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
  
  // Log all events with timestamps and transport info
  socket.onAny((eventName, ...args) => {
    const timestamp = new Date().toISOString();
    const transport = socket.io.engine.transport.name;
    console.log(`[${timestamp}] [${transport}] 🔔 Event [${eventName}]:`, JSON.stringify(args, null, 2));
  });
  
  function setConnectionStatus(status) {
    const transport = socket.io.engine.transport.name;
    console.log(`🔌 Connection Status: ${status} (transport: ${transport})`);
  }
  
  socket.on('joined', async (data) => {
    console.log('✅ Joined room:', data.session_id);
    if (processingStarted) return;
    processingStarted = true;
    
    console.log('🔧 Starting processing...');
    
    // Wait a bit to allow transport upgrade
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    try {
      const processingSources = [{
        type: 'web',
        name: 'Full WebSocket Test Source',
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
      console.log('⏳ Waiting for processing updates via WebSocket...');
      
      // Add a periodic transport check
      const transportCheck = setInterval(() => {
        const currentTransport = socket.io.engine.transport.name;
        console.log(`🔍 Transport check - Current: ${currentTransport}, Connected: ${socket.connected}, Updates: ${updateCount}`);
        if (!socket.connected) {
          console.log('❌ Socket disconnected during processing');
          clearInterval(transportCheck);
        }
      }, 10000);
      
      // Clear the interval after 120 seconds
      setTimeout(() => clearInterval(transportCheck), 120000);
      
    } catch (error) {
      console.error('❌ Failed to start processing:', error.message);
      socket.disconnect();
      process.exit(1);
    }
  });
  
  socket.on('processing_update', (data) => {
    updateCount++;
    const timestamp = new Date().toISOString();
    const transport = socket.io.engine.transport.name;
    console.log(`[${timestamp}] [${transport}] 📡 Update #${updateCount} [${data.type}]: ${data.message}`);
    
    // Check if this is the test message
    if (data.message && data.message.includes('Test: WebSocket connection verified')) {
      testMessageReceived = true;
      console.log('✅ Test message received successfully');
    }
    
    if (data.type === 'complete') {
      processingCompleted = true;
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
      
      // Show final results
      showFinalResults();
      socket.disconnect();
      
    } else if (data.type === 'error') {
      console.log('❌ Processing error:', data.message);
      showFinalResults();
      socket.disconnect();
      process.exit(1);
    }
  });
  
  function showFinalResults() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 FINAL TEST RESULTS');
    console.log('='.repeat(60));
    console.log(`✅ Test message received: ${testMessageReceived}`);
    console.log(`🚀 Transport upgraded: ${transportUpgraded}`);
    console.log(`📡 Total updates received: ${updateCount}`);
    console.log(`🎯 Processing completed: ${processingCompleted}`);
    console.log(`🔌 Final transport: ${socket.io.engine.transport.name}`);
    console.log('='.repeat(60));
    
    if (testMessageReceived && updateCount > 1 && processingCompleted) {
      console.log('🎉 SUCCESS: Full WebSocket functionality working!');
      if (transportUpgraded) {
        console.log('🚀 BONUS: Transport successfully upgraded to WebSocket!');
      }
      process.exit(0);
    } else if (testMessageReceived && updateCount > 1) {
      console.log('⚠️  PARTIAL SUCCESS: WebSocket communication working but processing incomplete');
      process.exit(0);
    } else {
      console.log('❌ FAILURE: WebSocket communication issues detected');
      process.exit(1);
    }
  }
  
  socket.on('connect_error', (error) => {
    console.error('❌ WebSocket connection failed:', error.message);
    process.exit(1);
  });
  
  socket.on('disconnect', (reason) => {
    console.log('🔌 WebSocket disconnected:', reason);
    console.log(`📊 Final stats: ${updateCount} updates received, test message: ${testMessageReceived}`);
    
    if (!processingCompleted) {
      console.log('⚠️  Disconnected before processing completed');
    }
  });
  
  socket.on('reconnect', (attemptNumber) => {
    console.log(`🔄 Reconnected after ${attemptNumber} attempts`);
    const transport = socket.io.engine.transport.name;
    console.log(`🔌 Reconnected with transport: ${transport}`);
  });
  
  socket.on('reconnect_attempt', (attemptNumber) => {
    console.log(`🔄 Reconnection attempt ${attemptNumber}`);
  });
  
  socket.on('reconnect_failed', () => {
    console.log('❌ Reconnection failed');
    showFinalResults();
  });
  
  // Timeout after 120 seconds
  setTimeout(() => {
    console.log(`⏰ Test timeout - received ${updateCount} updates`);
    console.log(`📊 Test message received: ${testMessageReceived}`);
    console.log(`🚀 Transport upgraded: ${transportUpgraded}`);
    
    if (updateCount === 0) {
      console.log('❌ COMPLETE FAILURE: No updates received at all');
      process.exit(1);
    } else if (testMessageReceived && updateCount === 1) {
      console.log('⚠️  PARTIAL FAILURE: Only test message received, no processing updates');
      process.exit(1);
    } else if (updateCount > 1) {
      console.log('✅ PARTIAL SUCCESS: Some updates received');
      showFinalResults();
    }
  }, 120000);
}

// Run the test
testFullWebSocket().catch(error => {
  console.error('💥 Test failed:', error.message);
  process.exit(1);
});