#!/usr/bin/env python3
"""
Enhanced web document loader with JavaScript support using Selenium
"""

import os
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from langchain.schema import Document
from langchain_community.document_loaders.url_selenium import SeleniumURLLoader


class EnhancedSeleniumWebLoader:
    """
    Enhanced web document loader that handles JavaScript-heavy websites
    using Selenium with additional features for better content extraction.
    """
    
    def __init__(
        self,
        browser: str = 'chrome',
        headless: bool = True,
        wait_time: int = 10,
        page_load_strategy: str = 'normal',
        custom_arguments: Optional[List[str]] = None
    ):
        """
        Initialize the enhanced Selenium web loader.
        
        Args:
            browser: Browser to use ('chrome' or 'firefox')
            headless: Run browser in headless mode
            wait_time: Maximum time to wait for page elements to load
            page_load_strategy: Page load strategy ('normal', 'eager', 'none')
            custom_arguments: Additional browser arguments
        """
        self.browser = browser
        self.headless = headless
        self.wait_time = wait_time
        self.page_load_strategy = page_load_strategy
        self.custom_arguments = custom_arguments or []
        
        # Default arguments for better performance and compatibility
        self.default_chrome_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-images',  # Skip images for faster loading
            '--disable-javascript-harmony-shipping',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-ipc-flooding-protection',
            '--window-size=1920,1080'
        ]
        
        self.default_firefox_args = [
            '--width=1920',
            '--height=1080'
        ]
    
    def _create_driver(self) -> webdriver:
        """Create and configure the WebDriver instance."""
        try:
            if self.browser.lower() == 'chrome':
                options = ChromeOptions()
                
                if self.headless:
                    options.add_argument('--headless')
                
                # Add default arguments
                for arg in self.default_chrome_args:
                    options.add_argument(arg)
                
                # Add custom arguments
                for arg in self.custom_arguments:
                    options.add_argument(arg)
                
                # Set page load strategy
                options.page_load_strategy = self.page_load_strategy
                
                # Try to find Chrome binary
                chrome_binary = self._find_chrome_binary()
                if chrome_binary:
                    options.binary_location = chrome_binary
                
                driver = webdriver.Chrome(options=options)
                
            elif self.browser.lower() == 'firefox':
                options = FirefoxOptions()
                
                if self.headless:
                    options.add_argument('--headless')
                
                # Add default arguments
                for arg in self.default_firefox_args:
                    options.add_argument(arg)
                
                # Add custom arguments
                for arg in self.custom_arguments:
                    options.add_argument(arg)
                
                # Set page load strategy
                options.page_load_strategy = self.page_load_strategy
                
                driver = webdriver.Firefox(options=options)
            else:
                raise ValueError(f"Unsupported browser: {self.browser}")
            
            # Set timeouts
            driver.implicitly_wait(self.wait_time)
            driver.set_page_load_timeout(self.wait_time * 2)
            
            return driver
            
        except Exception as e:
            raise WebDriverException(f"Failed to create WebDriver: {e}")
    
    def _find_chrome_binary(self) -> Optional[str]:
        """Find Chrome binary location."""
        possible_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/snap/bin/chromium',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        return None
    
    def load_url_with_js_wait(
        self, 
        url: str, 
        wait_for_element: Optional[str] = None,
        wait_for_text: Optional[str] = None,
        additional_wait: int = 2
    ) -> Document:
        """
        Load a single URL and wait for JavaScript content to load.
        
        Args:
            url: URL to load
            wait_for_element: CSS selector or XPath to wait for
            wait_for_text: Text content to wait for
            additional_wait: Additional seconds to wait after conditions are met
            
        Returns:
            Document with loaded content
        """
        driver = None
        try:
            driver = self._create_driver()
            
            print(f"Loading URL: {url}")
            driver.get(url)
            
            # Wait for specific element if provided
            if wait_for_element:
                try:
                    print(f"Waiting for element: {wait_for_element}")
                    WebDriverWait(driver, self.wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_element))
                    )
                except TimeoutException:
                    print(f"Warning: Element '{wait_for_element}' not found within {self.wait_time} seconds")
            
            # Wait for specific text if provided
            if wait_for_text:
                try:
                    print(f"Waiting for text: {wait_for_text}")
                    WebDriverWait(driver, self.wait_time).until(
                        lambda d: wait_for_text in d.page_source
                    )
                except TimeoutException:
                    print(f"Warning: Text '{wait_for_text}' not found within {self.wait_time} seconds")
            
            # Additional wait for dynamic content
            if additional_wait > 0:
                print(f"Additional wait: {additional_wait} seconds")
                time.sleep(additional_wait)
            
            # Get page content
            page_source = driver.page_source
            title = driver.title
            current_url = driver.current_url
            
            # Create document
            document = Document(
                page_content=page_source,
                metadata={
                    'source': url,
                    'title': title,
                    'current_url': current_url,
                    'loader': 'enhanced_selenium',
                    'timestamp': time.time()
                }
            )
            
            print(f"Successfully loaded: {title}")
            return document
            
        except Exception as e:
            print(f"Error loading {url}: {e}")
            # Return empty document with error info
            return Document(
                page_content="",
                metadata={
                    'source': url,
                    'error': str(e),
                    'loader': 'enhanced_selenium',
                    'timestamp': time.time()
                }
            )
        finally:
            if driver:
                driver.quit()
    
    def load_urls(
        self, 
        urls: List[str],
        wait_conditions: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Document]:
        """
        Load multiple URLs with JavaScript support.
        
        Args:
            urls: List of URLs to load
            wait_conditions: Dictionary mapping URLs to wait conditions
                           Format: {url: {'element': 'selector', 'text': 'text', 'wait': seconds}}
        
        Returns:
            List of Document objects
        """
        documents = []
        wait_conditions = wait_conditions or {}
        
        for url in urls:
            conditions = wait_conditions.get(url, {})
            
            doc = self.load_url_with_js_wait(
                url=url,
                wait_for_element=conditions.get('element'),
                wait_for_text=conditions.get('text'),
                additional_wait=conditions.get('wait', 2)
            )
            
            if doc.page_content:  # Only add non-empty documents
                documents.append(doc)
        
        return documents
    
    def load_spa_content(
        self, 
        url: str, 
        navigation_steps: Optional[List[Dict[str, Any]]] = None
    ) -> List[Document]:
        """
        Load content from Single Page Applications (SPAs) with navigation.
        
        Args:
            url: Base URL of the SPA
            navigation_steps: List of navigation steps
                            Format: [{'action': 'click', 'selector': 'button', 'wait': 2}, ...]
        
        Returns:
            List of Document objects from different states
        """
        driver = None
        documents = []
        
        try:
            driver = self._create_driver()
            driver.get(url)
            
            # Initial page load
            time.sleep(3)
            initial_doc = Document(
                page_content=driver.page_source,
                metadata={
                    'source': url,
                    'title': driver.title,
                    'state': 'initial',
                    'loader': 'enhanced_selenium_spa',
                    'timestamp': time.time()
                }
            )
            documents.append(initial_doc)
            
            # Execute navigation steps
            if navigation_steps:
                for i, step in enumerate(navigation_steps):
                    try:
                        action = step.get('action', 'click')
                        selector = step.get('selector')
                        wait_time = step.get('wait', 2)
                        
                        if action == 'click' and selector:
                            element = WebDriverWait(driver, self.wait_time).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            element.click()
                            time.sleep(wait_time)
                            
                            # Capture content after navigation
                            nav_doc = Document(
                                page_content=driver.page_source,
                                metadata={
                                    'source': url,
                                    'title': driver.title,
                                    'state': f'navigation_step_{i+1}',
                                    'navigation_action': f"{action}:{selector}",
                                    'loader': 'enhanced_selenium_spa',
                                    'timestamp': time.time()
                                }
                            )
                            documents.append(nav_doc)
                            
                    except Exception as e:
                        print(f"Navigation step {i+1} failed: {e}")
                        continue
            
            return documents
            
        except Exception as e:
            print(f"Error loading SPA content from {url}: {e}")
            return documents
        finally:
            if driver:
                driver.quit()


def create_enhanced_web_loader(
    browser: str = 'chrome',
    headless: bool = True,
    wait_time: int = 10
) -> EnhancedSeleniumWebLoader:
    """
    Factory function to create an enhanced web loader.
    
    Args:
        browser: Browser to use ('chrome' or 'firefox')
        headless: Run browser in headless mode
        wait_time: Maximum time to wait for page elements
        
    Returns:
        EnhancedSeleniumWebLoader instance
    """
    return EnhancedSeleniumWebLoader(
        browser=browser,
        headless=headless,
        wait_time=wait_time
    )


# Compatibility wrapper for LangChain SeleniumURLLoader
class CompatibleSeleniumLoader:
    """
    Wrapper around LangChain's SeleniumURLLoader with enhanced configuration.
    """
    
    def __init__(
        self,
        urls: List[str],
        browser: str = 'chrome',
        headless: bool = True,
        wait_time: int = 10,
        continue_on_failure: bool = True
    ):
        self.urls = urls
        self.browser = browser
        self.headless = headless
        self.wait_time = wait_time
        self.continue_on_failure = continue_on_failure
        
        # Configure browser arguments
        arguments = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-extensions',
            '--disable-images',
            f'--window-size=1920,1080'
        ]
        
        if headless:
            arguments.append('--headless')
        
        # Create the loader
        self.loader = SeleniumURLLoader(
            urls=urls,
            browser=browser,
            headless=headless,
            continue_on_failure=continue_on_failure,
            arguments=arguments
        )
    
    def load(self) -> List[Document]:
        """Load documents using SeleniumURLLoader."""
        try:
            return self.loader.load()
        except Exception as e:
            print(f"Error loading URLs with Selenium: {e}")
            return []


# Example usage and configuration
if __name__ == "__main__":
    # Example 1: Basic JavaScript-heavy website loading
    loader = create_enhanced_web_loader()
    
    # Load a single URL with custom wait conditions
    doc = loader.load_url_with_js_wait(
        url="https://example-spa.com",
        wait_for_element=".content-loaded",
        additional_wait=3
    )
    
    # Example 2: Multiple URLs with different wait conditions
    urls = [
        "https://react-app.com",
        "https://vue-app.com",
        "https://angular-app.com"
    ]
    
    wait_conditions = {
        "https://react-app.com": {"element": ".react-content", "wait": 2},
        "https://vue-app.com": {"text": "Vue App Loaded", "wait": 3},
        "https://angular-app.com": {"element": "app-root", "wait": 4}
    }
    
    docs = loader.load_urls(urls, wait_conditions)
    
    # Example 3: SPA with navigation
    spa_docs = loader.load_spa_content(
        url="https://spa-example.com",
        navigation_steps=[
            {"action": "click", "selector": "#menu-docs", "wait": 2},
            {"action": "click", "selector": "#submenu-api", "wait": 2}
        ]
    )
    
    print(f"Loaded {len(docs)} documents from regular URLs")
    print(f"Loaded {len(spa_docs)} documents from SPA navigation")
