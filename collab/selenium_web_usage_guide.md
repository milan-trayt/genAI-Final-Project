# Enhanced Web Loading with JavaScript Support

This guide explains how to use the enhanced Selenium-based web loader to handle JavaScript-heavy websites in your RAG ingestion pipeline.

## Overview

The standard `WebBaseLoader` only captures the initial HTML and doesn't wait for JavaScript to render dynamic content. This is problematic for modern websites that rely heavily on client-side JavaScript frameworks like React, Vue, Angular, or other SPAs (Single Page Applications).

Our enhanced solution provides:
- **SeleniumURLLoader**: LangChain's built-in Selenium loader
- **EnhancedSeleniumWebLoader**: Custom loader with advanced features
- **Automatic fallback**: Falls back to basic web loader if Selenium fails

## Installation

First, install the additional requirements:

```bash
pip install -r requirements_selenium.txt
```

You'll also need to have Chrome or Firefox installed on your system.

## Basic Usage

### 1. Using the Interactive Menu

When adding web sources through the interactive menu (option 2), the system will automatically use Selenium for JavaScript-heavy sites:

```python
python interactive_ingestion.py
# Select option 2: Add web documents
# Enter URLs - the system will automatically use Selenium
```

### 2. Programmatic Usage

```python
from models import create_web_source
from interactive_ingestion import InteractiveRAGIngestion

# Create web source with Selenium support (default)
source = create_web_source(
    url="https://react-docs-site.com",
    doc_type="react_documentation",
    use_selenium=True,
    wait_for_element=".main-content",  # Wait for this CSS selector
    additional_wait=3,  # Additional seconds to wait
    browser="chrome"  # or "firefox"
)

# Add to ingestion pipeline
ingestion = InteractiveRAGIngestion()
ingestion.document_sources.append(source)
ingestion.process_documents()
```

## Advanced Configuration

### Wait Conditions

You can specify different wait conditions for better content loading:

```python
# Wait for specific element
source = create_web_source(
    url="https://spa-app.com",
    wait_for_element=".content-loaded"  # CSS selector
)

# Wait for specific text
source = create_web_source(
    url="https://dynamic-site.com",
    wait_for_text="Content loaded successfully"
)

# Combine both conditions
source = create_web_source(
    url="https://complex-app.com",
    wait_for_element=".main-content",
    wait_for_text="Ready",
    additional_wait=5  # Extra wait time
)
```

### Browser Selection

```python
# Use Chrome (default)
source = create_web_source(url="https://example.com", browser="chrome")

# Use Firefox
source = create_web_source(url="https://example.com", browser="firefox")
```

### Disable Selenium (fallback to basic loader)

```python
source = create_web_source(
    url="https://simple-static-site.com",
    use_selenium=False  # Use basic WebBaseLoader
)
```

## Direct Selenium Loader Usage

For more control, you can use the Selenium loaders directly:

### Enhanced Selenium Loader

```python
from selenium_web_loader import EnhancedSeleniumWebLoader

loader = EnhancedSeleniumWebLoader(
    browser='chrome',
    headless=True,
    wait_time=15
)

# Load single URL with custom wait conditions
doc = loader.load_url_with_js_wait(
    url="https://react-app.com",
    wait_for_element=".app-loaded",
    additional_wait=3
)

# Load multiple URLs
urls = ["https://site1.com", "https://site2.com"]
docs = loader.load_urls(urls)
```

### SPA Navigation Support

For Single Page Applications that require navigation:

```python
# Load SPA with navigation steps
spa_docs = loader.load_spa_content(
    url="https://spa-docs.com",
    navigation_steps=[
        {"action": "click", "selector": "#docs-menu", "wait": 2},
        {"action": "click", "selector": "#api-section", "wait": 3}
    ]
)
```

### Compatible Selenium Loader

Using LangChain's built-in SeleniumURLLoader with enhanced configuration:

```python
from selenium_web_loader import CompatibleSeleniumLoader

loader = CompatibleSeleniumLoader(
    urls=["https://js-heavy-site.com"],
    browser='chrome',
    headless=True,
    wait_time=15
)

docs = loader.load()
```

## Common Use Cases

### 1. React/Vue/Angular Documentation Sites

```python
# React documentation
react_source = create_web_source(
    url="https://reactjs.org/docs/getting-started.html",
    doc_type="react_docs",
    wait_for_element=".main-content",
    additional_wait=2
)

# Vue documentation
vue_source = create_web_source(
    url="https://vuejs.org/guide/",
    doc_type="vue_docs",
    wait_for_element="#app",
    additional_wait=2
)
```

### 2. API Documentation with Interactive Examples

```python
api_docs_source = create_web_source(
    url="https://api-docs.example.com",
    doc_type="api_documentation",
    wait_for_element=".api-explorer",
    wait_for_text="API Explorer loaded",
    additional_wait=4
)
```

### 3. Dashboard or Admin Interfaces

```python
dashboard_source = create_web_source(
    url="https://admin.example.com/docs",
    doc_type="admin_documentation",
    wait_for_element=".dashboard-content",
    additional_wait=5
)
```

## Troubleshooting

### Common Issues

1. **Browser not found**: Install Chrome or Firefox
2. **Timeout errors**: Increase `wait_time` or `additional_wait`
3. **Element not found**: Check CSS selectors are correct
4. **Memory issues**: Use headless mode (default)

### Debugging

Enable verbose logging to see what's happening:

```python
import logging
logging.basicConfig(level=logging.INFO)

# The loader will print detailed information about loading progress
```

### Fallback Behavior

The system automatically falls back in this order:
1. EnhancedSeleniumWebLoader
2. CompatibleSeleniumLoader (LangChain's SeleniumURLLoader)
3. WebBaseLoader (basic HTTP loader)

## Performance Considerations

### Optimization Tips

1. **Use headless mode**: Faster and uses less memory (default)
2. **Disable images**: Already configured in default arguments
3. **Set appropriate timeouts**: Don't wait longer than necessary
4. **Batch processing**: Process multiple URLs in sequence

### Resource Usage

- Selenium uses more CPU and memory than basic web loading
- Each browser instance takes ~50-100MB RAM
- Loading time is typically 3-10 seconds per page vs <1 second for basic loading

## Example: Complete Workflow

```python
from models import create_web_source
from interactive_ingestion import InteractiveRAGIngestion

# Create ingestion pipeline
ingestion = InteractiveRAGIngestion()

# Add JavaScript-heavy documentation sites
js_sites = [
    create_web_source(
        url="https://docs.react.dev/",
        doc_type="react_docs",
        wait_for_element=".main-content"
    ),
    create_web_source(
        url="https://vuejs.org/guide/",
        doc_type="vue_docs",
        wait_for_element="#app"
    ),
    create_web_source(
        url="https://angular.io/docs",
        doc_type="angular_docs",
        wait_for_element=".docs-content",
        additional_wait=3
    )
]

# Add sources to pipeline
ingestion.document_sources.extend(js_sites)

# Process all documents
ingestion.process_documents()

# Test search
ingestion.test_search()
```

## JSON Configuration

You can also configure Selenium options via JSON input:

```json
{
  "sources": [
    {
      "type": "web",
      "path": "https://react-app.com",
      "docType": "react_documentation",
      "selenium": {
        "use_selenium": true,
        "wait_for_element": ".main-content",
        "wait_for_text": "App loaded",
        "additional_wait": 3,
        "browser": "chrome"
      }
    }
  ]
}
```

This enhanced web loading capability ensures that your RAG system can properly ingest content from modern JavaScript-heavy websites, providing much more comprehensive and accurate document processing for contemporary web applications and documentation sites.
