#!/usr/bin/env python3
# utils/selenium_utils.py - Selenium utilities for LeadFinder

import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from rich.console import Console

from config import SELENIUM_HEADLESS, SELENIUM_WINDOW_SIZE, SELENIUM_USER_AGENT, logger

console = Console()

def setup_selenium():
    """Set up and return a Selenium WebDriver"""
    try:
        options = Options()
        
        # Configure headless mode
        if SELENIUM_HEADLESS:
            options.add_argument("--headless")
        
        # Configure window size
        options.add_argument(f"--window-size={SELENIUM_WINDOW_SIZE}")
        
        # Additional settings for stability
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Add user agent to avoid detection
        options.add_argument(f"user-agent={SELENIUM_USER_AGENT}")
        
        # Install the latest ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set page load timeout
        driver.set_page_load_timeout(30)
        
        return driver
    except Exception as e:
        logger.error(f"Error setting up Selenium: {e}")
        console.print(f"[bold red]Error setting up Selenium: {e}[/bold red]")
        console.print("[yellow]Make sure you have Chrome installed on your system.[/yellow]")
        sys.exit(1)

def wait_for_element(driver, by, value, timeout=10):
    """Wait for an element to be present on the page"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        logger.warning(f"Timeout waiting for element: {value}")
        return None

def wait_for_elements(driver, by, value, timeout=10):
    """Wait for elements to be present on the page"""
    try:
        elements = WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((by, value))
        )
        return elements
    except TimeoutException:
        logger.warning(f"Timeout waiting for elements: {value}")
        return []

def wait_for_clickable(driver, by, value, timeout=10):
    """Wait for an element to be clickable"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        return element
    except TimeoutException:
        logger.warning(f"Timeout waiting for clickable element: {value}")
        return None

def safe_click(driver, element):
    """Safely click an element with retry"""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            element.click()
            return True
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.warning(f"Failed to click element after {max_attempts} attempts: {e}")
                return False
            time.sleep(1)

def scroll_to_element(driver, element):
    """Scroll to make an element visible"""
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        # Add a small delay to let the page settle
        time.sleep(0.5)
        return True
    except Exception as e:
        logger.warning(f"Failed to scroll to element: {e}")
        return False

def scroll_down(driver, pixels=300):
    """Scroll down the page by a number of pixels"""
    try:
        driver.execute_script(f"window.scrollBy(0, {pixels});")
        # Add a small delay to let the page settle
        time.sleep(0.5)
        return True
    except Exception as e:
        logger.warning(f"Failed to scroll down: {e}")
        return False

def scroll_to_bottom(driver):
    """Scroll to the bottom of the page"""
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # Add a small delay to let the page settle
        time.sleep(0.5)
        return True
    except Exception as e:
        logger.warning(f"Failed to scroll to bottom: {e}")
        return False

def get_text_safely(element, default=""):
    """Safely get text from an element with a default value"""
    try:
        if element:
            return element.text.strip()
        return default
    except Exception:
        return default

def get_attribute_safely(element, attribute, default=""):
    """Safely get an attribute from an element with a default value"""
    try:
        if element:
            value = element.get_attribute(attribute)
            return value.strip() if value else default
        return default
    except Exception:
        return default