# GenAI React Frontend

Modern React frontend for the GenAI DevOps Assistant with multi-tab chat interface and document ingestion capabilities.

## 🚀 Quick Start with Docker

### Prerequisites
- Docker and Docker Compose
- Environment variables configured in `.env` file

### Start All Services
```bash
# From the root directory
docker-compose up --build
```

### Access the Application
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **Collab/Ingestion:** http://localhost:8503
- **Jupyter Notebook:** http://localhost:8888

## 🏗️ Architecture

### Components
- **ChatInterface**: Multi-tab conversational interface with AWS service recommendations
- **IngestionInterface**: Document ingestion with support for web, GitHub, PDF, and CSV sources
- **QueryTypeSelector**: Query type selection for specialized responses

### Features
- ✅ **Multi-tab Chat Sessions**: Independent conversation contexts
- ✅ **Document Ingestion**: Web scraping, GitHub repos, PDFs, CSVs
- ✅ **Auto-close on Success**: Ingestion page closes automatically after processing
- ✅ **Multiple Source Addition**: Add multiple URLs/repos per submission
- ✅ **Proper Error Handling**: Clear error messages and validation
- ✅ **Responsive Design**: Mobile-friendly interface
- ✅ **Real-time Processing**: Live updates during document processing

## 🛠️ Development

### Local Development (without Docker)
```bash
cd react-frontend
npm install
npm start
```

### Environment Variables
Create `.env.local` for local development:
```bash
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_COLLAB_URL=http://localhost:8503
```

### Build for Production
```bash
npm run build
```

## 📋 Usage Guide

### Chat Interface
1. **Create Session**: Click "New Chat" to start a conversation
2. **Select Query Type**: Choose from General, Service Recommendation, Pricing, or Terraform
3. **Ask Questions**: Get AWS service recommendations with step-by-step reasoning
4. **Quick Response**: Use the ⚡ Quick Response for one-off questions

### Document Ingestion
1. **Web Documents**: 
   - Enter URLs (one per line)
   - Supports JavaScript-heavy sites with Selenium
   - Specify document type for better categorization

2. **GitHub Repositories**:
   - Format: `owner/repo`
   - Optional GitHub token for private repos
   - Filter by file extensions

3. **File Upload**:
   - Drag & drop PDF/CSV files
   - Or enter file paths for large files
   - Multiple files supported

4. **Processing**:
   - Real-time progress updates
   - Automatic cleanup on success
   - Clear error messages on failure

## 🔧 Configuration

### Query Types
- **General**: Standard AWS infrastructure questions
- **Service Recommendation**: Get personalized AWS service suggestions
- **Pricing**: Cost estimates and optimization tips
- **Terraform**: Generate infrastructure-as-code

### Supported Document Sources
- **Web**: Any HTTP/HTTPS URL with JavaScript support
- **GitHub**: Public/private repositories with file filtering
- **PDF**: Document upload or file path
- **CSV**: Data files with chunked processing

## 🐛 Troubleshooting

### Common Issues

1. **Frontend not loading**:
   ```bash
   docker-compose logs frontend
   ```

2. **API connection errors**:
   - Check backend service is running: `curl http://localhost:8000/health`
   - Verify CORS settings in backend

3. **Ingestion failures**:
   - Check collab service logs: `docker-compose logs collab`
   - Verify API keys in environment variables

4. **Build failures**:
   ```bash
   # Clear Docker cache
   docker-compose down
   docker system prune -f
   docker-compose up --build
   ```

### Development Tips

1. **Hot Reloading**: Changes to React files automatically reload in development
2. **API Debugging**: Use browser DevTools Network tab to inspect API calls
3. **State Management**: React state is used for session management and UI state

## 📦 Dependencies

### Core
- **React 18**: Modern React with hooks
- **React Router**: Client-side routing
- **Axios**: HTTP client for API calls

### UI Components
- **Lucide React**: Modern icon library
- **React Markdown**: Markdown rendering for chat messages
- **React Dropzone**: File upload with drag & drop

### Development
- **React Scripts**: Create React App tooling
- **ESLint**: Code linting
- **Prettier**: Code formatting

## 🔄 API Integration

### Backend Endpoints
- `POST /query/conversational`: Chat with session context
- `POST /query/one-time`: Quick responses without sessions
- `GET /sessions`: List all chat sessions
- `POST /sessions`: Create new session
- `DELETE /sessions/{id}`: Delete session

### Collab Endpoints
- `POST /api/process`: Process document ingestion
- `GET /api/status`: Check ingestion system status
- `GET /health`: Health check

## 🚀 Deployment

### Production Build
```bash
# Build production image
docker build -f Dockerfile -t genai-frontend:prod .

# Run with nginx
docker run -p 80:80 genai-frontend:prod
```

### Environment-specific Builds
- **Development**: Uses `Dockerfile.dev` with hot reloading
- **Production**: Uses `Dockerfile` with nginx and optimized build

## 📄 License

This project is part of the GenAI DevOps Assistant and follows the same license terms.