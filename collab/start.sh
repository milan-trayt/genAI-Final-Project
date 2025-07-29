#!/bin/bash

echo "🚀 Starting GenAI DevOps Assistant with Selenium Support"
echo "======================================================="

# Test Selenium setup
echo "🧪 Testing Selenium/Chrome setup..."
python3 -c "
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    print('✅ Selenium imports successful')
    
    # Test Chrome setup
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get('data:text/html,<html><body><h1>Test</h1></body></html>')
        print('✅ Chrome WebDriver test successful')
        driver.quit()
        print('🎉 Selenium setup verified - JavaScript-heavy websites will work!')
    except Exception as e:
        print(f'⚠️ Chrome WebDriver test failed: {e}')
        print('📝 Falling back to basic web loading for JavaScript-heavy sites')
        
except ImportError as ie:
    print(f'❌ Selenium import error: {ie}')
    print('📝 JavaScript-heavy websites will use fallback loading')
" 2>/dev/null || echo "⚠️ Selenium test skipped - will use fallback loading"

echo ""

# Start Flask API server in the background
echo "🌐 Starting API server..."
python /workspace/api_server.py &
API_PID=$!
echo "✅ API server started with PID: $API_PID"

# Give API server time to start
sleep 2

# Start Jupyter Lab
echo "📚 Starting Jupyter Lab..."
echo "🔗 Access URLs:"
echo "   - Jupyter Lab: http://localhost:8888"
echo "   - API Server: http://localhost:8503"
echo ""
echo "💡 Your RAG system now supports JavaScript-heavy websites!"
echo "   Use interactive_ingestion.py to add web sources with JS support."
echo ""

jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''
