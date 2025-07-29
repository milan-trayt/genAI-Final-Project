# Docker Setup for JavaScript Web Loading

## 🐳 Automated Docker Setup

The Docker configuration has been updated to automatically install and configure Selenium with Chrome for JavaScript-heavy website loading.

## 🚀 Quick Start

### 1. Build and Start Services
```bash
# Build and start all services
docker-compose up --build

# Or start in detached mode
docker-compose up --build -d
```

### 2. Verify Selenium Setup
The container will automatically test Selenium during startup. Look for these messages:
```
🧪 Testing Selenium/Chrome setup...
✅ Selenium imports successful
✅ Chrome WebDriver test successful
🎉 Selenium setup verified - JavaScript-heavy websites will work!
```

### 3. Access Services
- **Jupyter Lab**: http://localhost:8888
- **API Server**: http://localhost:8503
- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000

## 🔧 What's Included

### Docker Configuration Updates:

1. **Dockerfile** (`collab/Dockerfile`):
   - Installs Chrome browser and dependencies
   - Includes all Selenium requirements
   - Configures proper Chrome setup for containers

2. **docker-compose.yml**:
   - Adds Chrome-specific environment variables
   - Configures shared memory for Chrome (`/dev/shm`)
   - Sets security options for Chrome in containers
   - Adds necessary capabilities (`SYS_ADMIN`)

3. **start.sh**:
   - Tests Selenium setup on container startup
   - Provides clear feedback on JavaScript support status
   - Graceful fallback if Selenium isn't working

## 🧪 Testing JavaScript Support

Once the container is running, test JavaScript website loading:

```bash
# Enter the collab container
docker exec -it genai-collab bash

# Run the test suite
python test_selenium_web_loader.py

# Or test interactively
python interactive_ingestion.py
# Select option 2: Add web documents
# Enter a JavaScript-heavy URL like https://docs.react.dev
```

## 🐛 Troubleshooting

### Container Issues:

1. **Chrome crashes in container**:
   ```bash
   # Check if security options are properly set
   docker-compose logs collab
   ```

2. **Shared memory issues**:
   ```bash
   # Verify /dev/shm is mounted
   docker exec -it genai-collab df -h /dev/shm
   ```

3. **Permission issues**:
   ```bash
   # Check Chrome binary permissions
   docker exec -it genai-collab ls -la /usr/bin/google-chrome
   ```

### Selenium Issues:

1. **WebDriver not found**:
   - The webdriver-manager automatically downloads ChromeDriver
   - Check container logs for download issues

2. **Chrome won't start**:
   - Verify security options in docker-compose.yml
   - Check if SYS_ADMIN capability is added

3. **Timeout errors**:
   - Increase wait times in web source configuration
   - Check container resource limits

## 🔍 Debug Mode

To debug Selenium issues in the container:

```bash
# Enter container
docker exec -it genai-collab bash

# Run Chrome manually to test
google-chrome --version
google-chrome --headless --no-sandbox --disable-dev-shm-usage --dump-dom https://example.com

# Test Python Selenium
python3 -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
driver.get('https://example.com')
print('Page title:', driver.title)
driver.quit()
"
```

## 📊 Performance Considerations

### Container Resources:
- Chrome requires additional memory (~100-200MB per instance)
- Consider increasing container memory limits for heavy usage
- Use headless mode (default) for better performance

### Optimization:
```yaml
# In docker-compose.yml, add resource limits if needed
services:
  collab:
    # ... existing config ...
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

## 🎯 Usage in RAG Pipeline

Once the Docker setup is complete, your RAG system automatically supports JavaScript-heavy websites:

```python
# In Jupyter notebook or interactive_ingestion.py
from models import create_web_source

# JavaScript-heavy sites now work automatically
react_docs = create_web_source(
    url="https://docs.react.dev/",
    doc_type="react_documentation",
    use_selenium=True,  # Default in Docker
    wait_for_element=".main-content"
)

# Add to ingestion pipeline
ingestion.document_sources.append(react_docs)
ingestion.process_documents()
```

## 🎉 Benefits

With this Docker setup:
- ✅ **Zero manual configuration** - everything is automated
- ✅ **Consistent environment** - works the same everywhere
- ✅ **JavaScript support** - handles React, Vue, Angular sites
- ✅ **Graceful fallback** - still works if Selenium fails
- ✅ **Production ready** - proper security and resource management

Your RAG system can now properly ingest content from modern JavaScript-heavy documentation sites and web applications!
