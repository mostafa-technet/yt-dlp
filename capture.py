import os
from playwright.sync_api import sync_playwright

# Get the URL from environment variable, default to Google
raw_url = os.environ.get("TARGET_URL", "https://www.google.com")

# Ensure the URL has the correct protocol
url = raw_url
if not url.startswith("http://") and not url.startswith("https://"):
    url = "https://" + url

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print(f"Navigating to {url}...")
    # Using the corrected 'url' variable
    page.goto(url, wait_until="networkidle", timeout=60000)
    
    # Save the files in an 'output' directory
    os.makedirs("output", exist_ok=True)
    page.screenshot(path="output/page.png", full_page=True)
    
    with open("output/rendered.html", "w", encoding="utf-8") as f:
        f.write(page.content())
        
    print(f"Capture finished. Files saved in 'output/' for {url}")
    browser.close()
