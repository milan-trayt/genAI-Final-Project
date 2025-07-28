# GenAI DevOps Assistant - Streamlit Frontend

A modern Streamlit-based frontend for the GenAI DevOps Assistant RAG system.

## Features

### 🗂️ **Tab-Based Conversations (Sessions)**
- Create multiple conversation sessions
- Each session maintains its own conversation history
- Switch between sessions seamlessly
- Delete sessions when no longer needed
- Session message counters

### ⚡ **One-Shot Queries**
- Ask questions without conversation context
- Popup modal interface
- Responses are not saved to any session
- Perfect for quick, standalone questions

### 💬 **Conversational Interface**
- Context-aware conversations within sessions
- Typing animation for responses
- Processing time indicators
- Source citations with expandable details
- Real-time health status monitoring

## Usage

### Starting a Conversation
1. Click "➕ New Session" in the sidebar
2. Select the newly created session
3. Start typing your questions in the chat input

### One-Shot Queries
1. Click "⚡ One-Shot Query" in the sidebar
2. Type your question in the modal
3. Click "Send Query" to get an immediate response
4. Use "Clear" to reset the input or "Close" to exit

### Managing Sessions
- **Switch Sessions**: Click on any session name in the sidebar
- **Delete Sessions**: Click the 🗑️ button next to a session
- **Active Session**: Indicated by 🟢 green dot

## API Integration

The frontend communicates with the backend REST API:

- **Health Check**: `GET /health`
- **Create Session**: `POST /sessions`
- **List Sessions**: `GET /sessions`
- **Delete Session**: `DELETE /sessions/{session_id}`
- **Conversational Query**: `POST /query/conversational`
- **One-Shot Query**: `POST /query/one-time`

## Configuration

Environment variables:
- `BACKEND_URL`: Backend API URL (default: `http://backend:8000`)

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set backend URL
export BACKEND_URL=http://localhost:8000

# Run Streamlit
streamlit run app.py
```

### Docker Development
```bash
# Build and run with docker-compose
docker compose up frontend -d

# View logs
docker logs genai-frontend

# Access the app
open http://localhost:8501
```

## Architecture

```
frontend/
├── app.py              # Main Streamlit application
├── config.py           # Configuration settings
├── api_client.py       # Backend API communication
├── session_manager.py  # Session state management
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container configuration
└── README.md          # This file
```

## Troubleshooting

### Backend Connection Issues
- Ensure the backend service is running and healthy
- Check the `BACKEND_URL` environment variable
- Verify network connectivity between containers

### Session State Issues
- Refresh the page to reset Streamlit session state
- Check browser console for JavaScript errors
- Ensure cookies are enabled

### Performance Issues
- Reduce `typing_delay` in config.py for faster response display
- Adjust `max_message_length` for longer conversations
- Monitor backend response times in the UI

## Features in Detail

### Session Management
- Sessions are created via the backend API
- Local session state tracks UI-specific data
- Message history is maintained per session
- Session deletion cleans up both backend and frontend state

### One-Shot Queries
- Independent of session context
- Uses separate API endpoint
- Modal-based interface prevents accidental context mixing
- Immediate response without conversation history

### Real-time Features
- Health status monitoring
- Processing time display
- Typing animation effects
- Source citation expansion