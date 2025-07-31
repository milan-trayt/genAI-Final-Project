# GenAI React Frontend

A modern React-based frontend for the GenAI DevOps Assistant with multi-tab chat sessions and document ingestion capabilities.

## Quick Start with Docker

```bash
# Start the frontend (from project root)
docker compose up frontend -d

# Or start all services
docker compose up -d
```

## Architecture

This React frontend provides:

- **Multi-tab Chat Sessions**: Independent conversation contexts
- **Document Ingestion**: Web scraping, GitHub repos, PDFs, CSVs
- **Auto-close on Success**: Ingestion page closes automatically after processing
- **Multiple Source Addition**: Add multiple URLs/repos per submission
- **Proper Error Handling**: Clear error messages and validation
- **Responsive Design**: Mobile-friendly interface
- **Real-time Processing**: Live updates during document processing

## Usage Guide

1. **Start a Chat**: Click "New Chat" to create a new conversation tab
2. **Switch Tabs**: Click on tab names to switch between conversations
3. **Document Ingestion**: Use the "Document Ingestion" tab to add sources
4. **Quick Response**: Use the Quick Response for one-off questions

## Configuration

The frontend connects to:
- Backend API: `http://localhost:8000`
- Collab API: `http://localhost:8503`

## Dependencies

- React 18
- Axios for HTTP requests
- Socket.IO for real-time communication
- React Dropzone for file uploads
- Lucide React for icons

## API Integration

- `/query/conversational` - Chat with session context
- `/query/one-time` - Quick responses without session
- `/sessions` - Session management
- `/api/process` - Document processing

## Deployment

```bash
# Development
npm start

# Production build
npm run build
```

## License

MIT License