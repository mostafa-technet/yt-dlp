import os
from playwright.sync_api import sync_playwright

URL = os.environ.get("TARGET_URL", "https://www.google.com")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print(f"Navigating to {URL}...")
    page.goto(URL, wait_until="networkidle", timeout=60000)
    
    # Save the files
    os.makedirs("output", exist_ok=True)
    page.screenshot(path="output/page.png", full_page=True)
    with open("output/rendered.html", "w", encoding="utf-8") as f:
        f.write(page.content())
        
    print("Capture finished. Files saved in 'output/'")
    browser.close()
