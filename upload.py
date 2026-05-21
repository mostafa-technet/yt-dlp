import os
import json
import re
import time
from playwright.sync_api import sync_playwright

# Configuration
COOKIE_SECRET = os.environ.get("YT_GOOGLE_CK")
TITLE = os.environ.get("YT_TITLE", "My Upload")
DESCRIPTION = os.environ.get("YT_DESCRIPTION", "")
VISIBILITY = os.environ.get("YT_VISIBILITY", "unlisted").lower()
VIDEO_FILE = "video.mp4"

def parse_netscape(text):
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = re.split(r"\s+", line)
        if len(parts) < 7: continue
        domain, flag, path, secure, expiry, name, value = parts[:7]
        cookies.append({
            "domain": domain, "path": path, "name": name, "value": value,
            "secure": secure.lower() == "true", "httpOnly": False, "expiry": int(expiry)
        })
    return cookies

def load_cookies():
    text = COOKIE_SECRET.strip()
    return json.loads(text) if text.startswith("[") else parse_netscape(text)

def run():
    with sync_playwright() as p:
        # Use 'chrome' channel for better YouTube compatibility
        browser = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Add cookies
        context.add_cookies(load_cookies())
        page = context.new_page()

        print("Navigating to YouTube Studio...")
        page.goto("https://studio.youtube.com", wait_until="networkidle")
        
        print("Uploading file...")
        page.goto("https://studio.youtube.com/channel/UC/videos/upload", wait_until="networkidle")
        
        # Robust file upload
        page.locator('input[type="file"]').set_input_files(VIDEO_FILE)
        
        # Use #textbox.nth(0) for Title and nth(1) for Description
        page.locator('#textbox').nth(0).wait_for(state="visible")
        page.locator('#textbox').nth(0).fill(TITLE)
        page.locator('#textbox').nth(1).fill(DESCRIPTION)
        
        print("Waiting for upload to process...")
        # Wait until the "Next" button is enabled or "Done" button is visible
        page.wait_for_selector('#done-button:not([disabled])', timeout=3600000)

        # Iterate through steps (Details -> Video Elements -> Checks -> Visibility)
        for _ in range(3):
            page.locator('#next-button').click()
            time.sleep(2)

        # Robust Visibility Selection using Roles
        print(f"Setting visibility to: {VISIBILITY}")
        page.get_by_role("radio", name=VISIBILITY.capitalize()).click()
        
        # Finalize
        page.locator("#done-button").click()
        
        # Wait for "Video Published" or similar dialog
        time.sleep(15)
        
        # Attempt to capture URL from final dialog
        final_url = page.locator('a[href*="youtu.be/"], a[href*="watch?v="]').first.get_attribute("href")
        if final_url:
            print(f"SUCCESS: VIDEO_URL={final_url}")
        else:
            print("Upload finished, but URL was not found on screen.")
            
        browser.close()

if __name__ == "__main__":
    run()
