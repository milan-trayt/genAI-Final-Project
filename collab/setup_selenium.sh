#!/bin/bash

echo "🚀 Setting up Selenium Web Loading for JavaScript-heavy websites"
echo "================================================================"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install selenium>=4.15.0 webdriver-manager>=4.0.0 unstructured>=0.10.0

# Check if Chrome is installed
echo "🔍 Checking for Chrome browser..."
if command -v google-chrome &> /dev/null || command -v google-chrome-stable &> /dev/null || command -v chromium-browser &> /dev/null; then
    echo "✅ Chrome/Chromium found"
    CHROME_AVAILABLE=true
else
    echo "❌ Chrome/Chromium not found"
    CHROME_AVAILABLE=false
fi

# Check if Firefox is installed
echo "🔍 Checking for Firefox browser..."
if command -v firefox &> /dev/null; then
    echo "✅ Firefox found"
    FIREFOX_AVAILABLE=true
else
    echo "❌ Firefox not found"
    FIREFOX_AVAILABLE=false
fi

# Install browser if none available
if [ "$CHROME_AVAILABLE" = false ] && [ "$FIREFOX_AVAILABLE" = false ]; then
    echo "⚠️ No supported browser found. Installing Chrome..."
    
    # Detect OS and install Chrome
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "🐧 Detected Linux - Installing Chrome..."
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
        sudo apt-get update
        sudo apt-get install -y google-chrome-stable
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "🍎 Detected macOS - Please install Chrome manually from https://www.google.com/chrome/"
        echo "   Or install via Homebrew: brew install --cask google-chrome"
    else
        echo "❓ Unknown OS - Please install Chrome or Firefox manually"
    fi
fi

# Test the setup
echo "🧪 Testing Selenium setup..."
python3 -c "
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    
    print('✅ Selenium imports successful')
    
    # Test Chrome setup
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get('https://httpbin.org/html')
        print('✅ Chrome WebDriver test successful')
        driver.quit()
    except Exception as e:
        print(f'❌ Chrome WebDriver test failed: {e}')
        
        # Try Firefox as fallback
        try:
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from webdriver_manager.firefox import GeckoDriverManager
            from selenium.webdriver.firefox.service import Service as FirefoxService
            
            firefox_options = FirefoxOptions()
            firefox_options.add_argument('--headless')
            
            firefox_service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=firefox_service, options=firefox_options)
            driver.get('https://httpbin.org/html')
            print('✅ Firefox WebDriver test successful')
            driver.quit()
        except Exception as fe:
            print(f'❌ Firefox WebDriver test also failed: {fe}')
            print('⚠️ Manual browser installation may be required')

except ImportError as ie:
    print(f'❌ Import error: {ie}')
    print('Please run: pip install selenium webdriver-manager')
"

echo ""
echo "🎉 Selenium setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Run your RAG ingestion: python interactive_ingestion.py"
echo "2. Add web sources (option 2) - Selenium will be used automatically"
echo "3. For testing: python test_selenium_web_loader.py"
echo ""
echo "📖 For detailed usage instructions, see: selenium_web_usage_guide.md"
