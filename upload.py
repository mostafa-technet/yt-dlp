import os
import json
import time
import re
from playwright.sync_api import sync_playwright

COOKIE_SECRET = os.environ["YT_GOOGLE_CK"]

TITLE = os.environ["YT_TITLE"]
DESCRIPTION = os.environ.get("YT_DESCRIPTION", "")
VISIBILITY = os.environ.get("YT_VISIBILITY", "unlisted")

VIDEO_FILE = "video.mp4"


def parse_netscape(text):
    cookies = []

    for line in text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")

        if len(parts) < 7:
            continue

        domain, flag, path, secure, expiry, name, value = parts

        cookies.append({
            "domain": domain,
            "path": path,
            "name": name,
            "value": value,
            "secure": secure.lower() == "true",
            "httpOnly": False
        })

    return cookies


def load_cookies():
    text = COOKIE_SECRET.strip()

    if text.startswith("["):
        return json.loads(text)

    return parse_netscape(text)


def wait_for_upload(page):
    print("Waiting for upload to finish...")

    start = time.time()

    while True:
        html = page.content()

        if "Upload complete" in html or "Checks complete" in html:
            print("Upload finished.")
            break

        if "Processing abandoned" in html or "Upload failed" in html:
            raise Exception("Upload failed")

        if time.time() - start > 3600:
            raise Exception("Upload timeout (1 hour)")

        time.sleep(5)


with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)

    context = browser.new_context()

    cookies = load_cookies()

    formatted = []

    for c in cookies:
        formatted.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "secure": c.get("secure", False)
        })

    context.add_cookies(formatted)

    page = context.new_page()

    print("Opening YouTube Studio...")
    page.goto("https://studio.youtube.com", wait_until="networkidle")

    time.sleep(5)

    print("Opening upload page...")
    page.goto(
        "https://studio.youtube.com/channel/UC/videos/upload",
        wait_until="networkidle"
    )

    time.sleep(5)

    print("Uploading video...")

    page.locator('input[type="file"]').first.set_input_files(VIDEO_FILE)

    time.sleep(10)

    title_box = page.locator(
        'div[aria-label="Add a title that describes your video (type @ to mention a channel)"]'
    ).first

    title_box.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    title_box.fill(TITLE)

    desc_box = page.locator(
        'div[aria-label="Tell viewers about your video (type @ to mention a channel)"]'
    ).first

    desc_box.click()
    desc_box.fill(DESCRIPTION)

    wait_for_upload(page)

    for _ in range(3):
        page.locator('#next-button').click()
        time.sleep(3)

    if VISIBILITY == "public":
        page.locator('tp-yt-paper-radio-button[name="PUBLIC"]').click()
    elif VISIBILITY == "private":
        page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
    else:
        page.locator('tp-yt-paper-radio-button[name="UNLISTED"]').click()

    time.sleep(2)

    page.locator('#done-button').click()

    print("Finalizing upload...")

    time.sleep(8)

    video_url = None

    try:
        link = page.locator('a:has-text("View on YouTube")').first
        video_url = link.get_attribute("href")
    except:
        pass

    if video_url:
        print(f"VIDEO_URL={video_url}")

        match = re.search(r"v=([^&]+)", video_url)
        if match:
            print(f"VIDEO_ID={match.group(1)}")

    else:
        print("Upload completed but video URL could not be detected.")

    print("SUCCESS: upload workflow finished")

    browser.close()
