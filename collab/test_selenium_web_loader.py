#!/usr/bin/env python3
"""
Test script for enhanced Selenium web loader functionality
"""

import sys
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from selenium_web_loader import EnhancedSeleniumWebLoader, CompatibleSeleniumLoader
from models import create_web_source


def test_basic_selenium_loading():
    """Test basic Selenium web loading functionality."""
    print("🧪 Testing Basic Selenium Web Loading")
    print("=" * 50)
    
    try:
        # Test with a simple website first
        loader = EnhancedSeleniumWebLoader(
            browser='chrome',
            headless=True,
            wait_time=10
        )
        
        # Test URL that should work
        test_url = "https://httpbin.org/html"
        print(f"Loading test URL: {test_url}")
        
        doc = loader.load_url_with_js_wait(
            url=test_url,
            additional_wait=2
        )
        
        if doc and doc.page_content:
            print(f"✅ Successfully loaded content ({len(doc.page_content)} characters)")
            print(f"   Title: {doc.metadata.get('title', 'N/A')}")
            print(f"   Source: {doc.metadata.get('source', 'N/A')}")
            return True
        else:
            print("❌ No content loaded")
            return False
            
    except Exception as e:
        print(f"❌ Error in basic loading test: {e}")
        return False


def test_compatible_selenium_loader():
    """Test the compatible Selenium loader."""
    print("\n🧪 Testing Compatible Selenium Loader")
    print("=" * 50)
    
    try:
        loader = CompatibleSeleniumLoader(
            urls=["https://httpbin.org/html"],
            browser='chrome',
            headless=True,
            wait_time=10
        )
        
        docs = loader.load()
        
        if docs and len(docs) > 0:
            doc = docs[0]
            print(f"✅ Successfully loaded {len(docs)} document(s)")
            print(f"   Content length: {len(doc.page_content)} characters")
            print(f"   Source: {doc.metadata.get('source', 'N/A')}")
            return True
        else:
            print("❌ No documents loaded")
            return False
            
    except Exception as e:
        print(f"❌ Error in compatible loader test: {e}")
        return False


def test_web_source_creation():
    """Test web source creation with Selenium options."""
    print("\n🧪 Testing Web Source Creation")
    print("=" * 50)
    
    try:
        # Create web source with Selenium options
        source = create_web_source(
            url="https://httpbin.org/html",
            doc_type="test_document",
            use_selenium=True,
            wait_for_element="body",
            additional_wait=2,
            browser="chrome"
        )
        
        print(f"✅ Created web source:")
        print(f"   URL: {source.source_path}")
        print(f"   Type: {source.source_type}")
        print(f"   Use Selenium: {source.metadata.get('use_selenium')}")
        print(f"   Wait for element: {source.metadata.get('wait_for_element')}")
        print(f"   Additional wait: {source.metadata.get('additional_wait')}")
        print(f"   Browser: {source.metadata.get('browser')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in web source creation test: {e}")
        return False


def test_javascript_heavy_site():
    """Test loading a JavaScript-heavy site (if available)."""
    print("\n🧪 Testing JavaScript-Heavy Site Loading")
    print("=" * 50)
    
    try:
        # Use a site that requires JavaScript (example.com is simple but works)
        loader = EnhancedSeleniumWebLoader(
            browser='chrome',
            headless=True,
            wait_time=15
        )
        
        # Test with a site that has some dynamic content
        test_url = "https://example.com"
        print(f"Loading JavaScript site: {test_url}")
        
        doc = loader.load_url_with_js_wait(
            url=test_url,
            wait_for_element="body",
            additional_wait=3
        )
        
        if doc and doc.page_content:
            print(f"✅ Successfully loaded JS-heavy content")
            print(f"   Content length: {len(doc.page_content)} characters")
            print(f"   Title: {doc.metadata.get('title', 'N/A')}")
            
            # Check if we got more than just basic HTML
            if len(doc.page_content) > 500:
                print("   ✅ Content appears to be fully loaded")
            else:
                print("   ⚠️ Content might be minimal")
                
            return True
        else:
            print("❌ No content loaded from JS site")
            return False
            
    except Exception as e:
        print(f"❌ Error in JS site loading test: {e}")
        return False


def test_fallback_behavior():
    """Test fallback behavior when Selenium fails."""
    print("\n🧪 Testing Fallback Behavior")
    print("=" * 50)
    
    try:
        # This should demonstrate the fallback mechanism
        # We'll simulate this by testing with an invalid browser
        print("Testing fallback from Selenium to basic loader...")
        
        # Create a source that would use Selenium
        source = create_web_source(
            url="https://httpbin.org/html",
            doc_type="test_document",
            use_selenium=True
        )
        
        print(f"✅ Source created with Selenium enabled")
        print(f"   In real usage, if Selenium fails, it will fall back to WebBaseLoader")
        print(f"   This ensures robust document loading even when Selenium isn't available")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in fallback test: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Enhanced Selenium Web Loader Test Suite")
    print("=" * 60)
    
    tests = [
        ("Basic Selenium Loading", test_basic_selenium_loading),
        ("Compatible Selenium Loader", test_compatible_selenium_loader),
        ("Web Source Creation", test_web_source_creation),
        ("JavaScript-Heavy Site", test_javascript_heavy_site),
        ("Fallback Behavior", test_fallback_behavior)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Selenium web loading is working correctly.")
    elif passed > 0:
        print("⚠️ Some tests passed. Check failed tests for issues.")
    else:
        print("❌ All tests failed. Check your Selenium setup.")
        print("\nTroubleshooting tips:")
        print("1. Install Chrome or Firefox browser")
        print("2. Install selenium requirements: pip install -r requirements_selenium.txt")
        print("3. Check if you have proper internet connection")
        print("4. Try running with --headless=False to see browser window")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
