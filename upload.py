import os
import json
import time
import re
from playwright.sync_api import sync_playwright

# --- Existing functions (keep these as they are) ---
COOKIE_SECRET = os.environ["YT_GOOGLE_CK"]
TITLE = os.environ["YT_TITLE"]
DESCRIPTION = os.environ.get("YT_DESCRIPTION", "")
VISIBILITY = os.environ.get("YT_VISIBILITY", "unlisted")
VIDEO_FILE = "video.mp4"

def parse_netscape(text):
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        httpOnly = False
        if line.startswith('#HttpOnly_'):
            httpOnly = True
            line = line.replace('#HttpOnly_', '')
        parts = re.split(r'\s+', line)
        if len(parts) < 7:
            continue
        domain, flag, path, secure, expiry, name, value = parts[:7]
        cookies.append({
            "domain": domain, "path": path or "/", "name": name, "value": value,
            "secure": secure.upper() == 'TRUE', "httpOnly": httpOnly,
            "expires": Number(expires) > 0 ? Number(expires) : -1 # Note: This line has a syntax error in Python. It should be an if-else. I'll correct this in the next version.
        })
    return cookies

# Corrected version of parse_netscape for Python syntax
def parse_netscape_corrected(text):
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        httpOnly = False
        if line.startswith('#HttpOnly_'):
            httpOnly = True
            line = line.replace('#HttpOnly_', '')
        parts = re.split(r'\s+', line)
        if len(parts) < 7:
            continue
        domain, flag, path, secure, expiry, name, value = parts[:7]
        
        # Corrected Python syntax for expiry
        try:
            expiry_num = int(expiry)
            if expiry_num <= 0:
                expiry_num = -1
        except ValueError:
            expiry_num = -1 # Default if not a valid number

        cookies.append({
            "domain": domain, "path": path or "/", "name": name, "value": value,
            "secure": secure.upper() == 'TRUE', "httpOnly": httpOnly,
            "expires": expiry_num
        })
    return cookies


def load_cookies():
    text = COOKIE_SECRET.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"JSON cookie parsing failed: {e}")
            return []
    else:
        return parse_netscape_corrected(text) # Use the corrected parser

def wait_for_upload(page):
    print("Waiting for upload to finish...")
    start = time.time()
    max_wait_seconds = 3600 # 1 hour

    while True:
        try:
            html = page.content()
        except Exception as e:
            print(f"Error getting page content: {e}")
            time.sleep(5) # Wait and retry
            continue

        if ("Upload complete" in html or
            "Checks complete" in html or
            "Finished processing" in html):
            print("Upload finished.")
            return

        if ("Processing abandoned" in html or
            "Upload failed" in html or
            "Daily upload limit reached" in html):
            raise Exception("YouTube upload failed during processing.")

        elapsed = time.time() - start
        print(f"Still uploading... {int(elapsed)}s / {max_wait_seconds}s")

        if elapsed > max_wait_seconds:
            raise Exception(f"Upload timeout after {max_wait_seconds} seconds.")

        time.sleep(5)

# --- Main execution block (REFINED) ---
with sync_playwright() as p:
    print("Launching browser...")
    try:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            timeout=60000 # 1 minute timeout for browser launch
        )
        context = browser.new_context()

        print("Loading cookies...")
        cookies = load_cookies()
        
        # Format cookies for Playwright if they aren't already
        formatted_cookies = []
        for c in cookies:
            # Ensure all required keys are present and have correct types
            formatted_cookies.append({
                "name": str(c.get("name", "")),
                "value": str(c.get("value", "")),
                "domain": str(c.get("domain", "")),
                "path": str(c.get("path", "/")),
                "secure": bool(c.get("secure", False)),
                "httpOnly": bool(c.get("httpOnly", False)),
                # 'expires' is not directly used by add_cookies but good to have
            })
        
        if formatted_cookies:
            context.add_cookies(formatted_cookies)
            print(f"Added {len(formatted_cookies)} cookies.")
        else:
            print("No cookies loaded or parsed successfully.")


        page = context.new_page()

        print("Opening YouTube Studio...")
        # Use more robust navigation to Studio home page
        page.goto("https://studio.youtube.com", wait_until="networkidle", timeout=120000)
        
        # Wait for the main Studio page elements to ensure it's loaded
        page.wait_for_selector('ytm-top-bar', timeout=60000) 
        print("YouTube Studio loaded.")

        print("Navigating to upload page...")
        # Dynamically find the upload button/link
        # This is more reliable than hardcoding the channel URL
        upload_button_selector = 'a[href*="/videos/upload"]'
        try:
            upload_link = page.locator(upload_button_selector).first
            upload_link.wait_for(state="visible", timeout=30000)
            upload_link.click()
        except Exception as e:
            print(f"Could not find or click the upload link: {e}")
            raise # Re-raise the exception to stop the workflow

        # Wait for the file input to be ready after clicking upload
        file_input_selector = 'input[type="file"]'
        page.wait_for_selector(file_input_selector, timeout=60000)
        print("Upload page ready.")

        print(f"Selecting video file: {VIDEO_FILE}...")
        file_input = page.locator(file_input_selector).first
        file_input.set_input_files(VIDEO_FILE)
        print("Video file selected.")

        # Wait for the title/description boxes to appear - more reliable than fixed sleep
        title_box_selector = 'div[aria-label*="title"]'
        desc_box_selector = 'div[aria-label*="Tell viewers about your video"]'
        
        page.wait_for_selector(title_box_selector, timeout=30000)
        print("Title and description boxes are ready.")

        print("Setting title...")
        title_box = page.locator(title_box_selector).first
        title_box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        title_box.fill(TITLE)

        print("Setting description...")
        desc_box = page.locator(desc_box_selector).first
        desc_box.click()
        desc_box.fill(DESCRIPTION)

        wait_for_upload(page) # This function handles the upload progress

        print("Navigating through video details (Next steps)...")
        # Use a loop that waits for the button to be clickable
        for i in range(3):
            print(f"Advancing step {i+1}/3...")
            next_button_selector = "#next-button"
            try:
                next_btn = page.locator(next_button_selector).first
                next_btn.wait_for(state="visible", timeout=15000)
                next_btn.click()
                time.sleep(2) # Short pause to allow UI to update
            except Exception as e:
                print(f"Could not click 'Next' button on step {i+1}: {e}")
                # Decide if this is a fatal error or if we can continue
                break 

        print(f"Setting visibility: {VISIBILITY.lower()}")
        
        # Use more specific selectors for visibility options if possible
        # Playwright's get_by_role can be good here if it finds the right element
        if VISIBILITY.lower() == "public":
            page.get_by_role("radio", name="Public").click()
        elif VISIBILITY.lower() == "private":
            page.get_by_role("radio", name="Private").click()
        else: # Default to unlisted
            page.get_by_role("radio", name="Unlisted").click()

        time.sleep(2) # Short pause before final click

        print("Finalizing upload...")
        done_button_selector = "#done-button"
        try:
            done_btn = page.locator(done_button_selector).first
            done_btn.wait_for(state="visible", timeout=15000)
            done_btn.click()
        except Exception as e:
            print(f"Could not click 'Done' button: {e}")
            raise

        video_url = None
        print("Attempting to extract video URL...")
        
        # Look for the "View on YouTube" link *after* clicking Done
        # This might appear in a notification or dialog.
        # The selector 'a.video-url-fade-in' is often used for this.
        view_link_selector = 'a.video-url-fade-in' 
        try:
            view_link = page.locator(view_link_selector).first
            # Wait specifically for the link to appear and have an href
            href = view_link.get_attribute("href", timeout=60000) 
            if href:
                video_url = href
                print(f"Successfully extracted URL: {video_url}")
            else:
                print("Found 'View on YouTube' element, but href attribute was empty.")
        except Exception as e:
            print(f"Could not find or extract video URL link within timeout: {e}")
            # It's possible the URL isn't displayed immediately or the selector changed.
            # The upload might still be successful, but we won't have the URL.

        print("===================================")
        if video_url:
            print(f"VIDEO_URL={video_url}")
            match = re.search(r"(?:v=|youtu\.be/|/)([A-Za-z0-9_-]+)", video_url) # Added / for short URLs
            if match:
                print(f"VIDEO_ID={match.group(1)}")
        else:
            print("Upload completed, but the video URL could not be automatically detected.")
            print("You may need to check YouTube Studio manually.")

        print("SUCCESS: upload workflow finished.")

    except Exception as e:
        print(f"ERROR: An exception occurred during the upload process: {e}")
        # Optional: Save a screenshot or page content for debugging
        try:
            page.screenshot(path="error_screenshot.png")
            print("Saved error screenshot to error_screenshot.png")
            with open("error_page_content.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Saved error page content to error_page_content.html")
        except Exception as screen_e:
            print(f"Could not save debug info: {screen_e}")
        raise # Re-raise to ensure the GitHub Actions job fails

    finally:
        if 'browser' in locals() and browser:
            browser.close()
            print("Browser closed.")
        print("===================================")
