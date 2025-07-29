# Quick Setup Guide for JavaScript Web Loading

## 🚀 Quick Installation

To fix the "No module named 'selenium'" error and enable JavaScript-heavy website loading:

### Option 1: Automatic Setup (Recommended)
```bash
cd collab
./setup_selenium.sh
```

### Option 2: Manual Installation
```bash
# Install dependencies
pip install selenium>=4.15.0 webdriver-manager>=4.0.0 unstructured>=0.10.0

# Or install all requirements
pip install -r requirements.txt
```

## 🔧 Browser Requirements

You need either Chrome or Firefox installed:

### Linux (Ubuntu/Debian):
```bash
# Install Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# Or install Firefox
sudo apt-get install firefox
```

### macOS:
```bash
# Install Chrome via Homebrew
brew install --cask google-chrome

# Or install Firefox
brew install --cask firefox
```

### Windows:
- Download Chrome: https://www.google.com/chrome/
- Download Firefox: https://www.mozilla.org/firefox/

## ✅ Verify Installation

Test that everything works:
```bash
cd collab
python test_selenium_web_loader.py
```

## 🎯 Usage

Once installed, your RAG system will automatically use Selenium for JavaScript-heavy websites:

```python
# Interactive mode
python interactive_ingestion.py
# Select option 2: Add web documents
# Enter JavaScript-heavy URLs - they'll work automatically!

# Programmatic usage
from models import create_web_source
source = create_web_source(
    url="https://react-docs.com",
    use_selenium=True,  # This is now the default
    wait_for_element=".main-content"
)
```

## 🐛 Troubleshooting

### Common Issues:

1. **"No module named 'selenium'"**
   ```bash
   pip install selenium webdriver-manager
   ```

2. **"WebDriver not found"**
   - The webdriver-manager will auto-download drivers
   - Make sure you have Chrome or Firefox installed

3. **"Browser not found"**
   - Install Chrome or Firefox (see browser requirements above)

4. **Timeout errors**
   - Increase wait times in your web source configuration
   - Check your internet connection

### Debug Mode:
```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.INFO)

# Test with non-headless mode to see browser
source = create_web_source(
    url="https://example.com",
    browser="chrome"  # Will show browser window for debugging
)
```

## 📖 Full Documentation

For complete usage instructions and examples, see:
- `selenium_web_usage_guide.md` - Comprehensive guide
- `selenium_web_loader.py` - Source code with examples
- `test_selenium_web_loader.py` - Test suite

## 🎉 What This Solves

Before: Your RAG system could only load static HTML, missing dynamic content from:
- React/Vue/Angular documentation sites
- Single Page Applications (SPAs)
- JavaScript-rendered content
- Dynamic API documentation

After: Full support for modern JavaScript-heavy websites with:
- Automatic JavaScript execution
- Configurable wait conditions
- Fallback to basic loading if needed
- Support for complex SPAs with navigation

Your RAG system can now properly ingest content from modern web applications!
