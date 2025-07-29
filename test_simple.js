const io = require('socket.io-client');

console.log('🧪 Simple websocket test');

const socket = io('http://localhost:8503', {
  transports: ['polling'],
  timeout: 10000,
  reconnection: false
});

// Listen for ALL events
socket.onAny((eventName, ...args) => {
  console.log(`📡 Event: ${eventName}`, JSON.stringify(args, null, 2));
});

socket.on('connect', () => {
  console.log('✅ Connected');
  
  // Just join a session and wait
  socket.emit('join_session', { session_id: 'test_simple' });
  
  // Send a test message to trigger some activity
  setTimeout(() => {
    console.log('📤 Sending test message...');
    socket.emit('test_message', { data: 'hello' });
  }, 2000);
});

setTimeout(() => {
  console.log('⏰ Test complete');
  socket.disconnect();
  process.exit(0);
}, 10000);