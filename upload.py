import os
import json
import time
import re
from playwright.sync_api import sync_playwright

COOKIE_SECRET = os.environ['YT_GOOGLE_CK']

TITLE = os.environ['YT_TITLE']
DESCRIPTION = os.environ.get('YT_DESCRIPTION', '')
VISIBILITY = os.environ.get('YT_VISIBILITY', 'unlisted')

VIDEO_FILE = 'video.mp4'


def parse_netscape(text):
    cookies = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith('#'):
            continue

        # supports tabs or spaces
        parts = re.split(r'\s+', line)

        if len(parts) < 7:
            continue

        domain, flag, path, secure, expiry, name, value = parts[:7]
		flag = ''
        cookie = {
            'domain': domain,
            'path': path,
            'name': name,
            'value': value,
            'secure': secure.lower() == 'true',
            'httpOnly': False,
        }

        cookies.append(cookie)

    return cookies


def load_cookies():
    text = COOKIE_SECRET.strip()

    # JSON cookie export
    if text.startswith('['):
        return json.loads(text)

    # Netscape cookies.txt
    return parse_netscape(text)


def wait_for_upload(page):
    print('Waiting for upload to finish...')

    start = time.time()

    while True:
        html = page.content()

        if (
            'Upload complete' in html
            or 'Checks complete' in html
            or 'Finished processing' in html
        ):
            print('Upload finished.')
            return

        if (
            'Processing abandoned' in html
            or 'Upload failed' in html
            or 'Daily upload limit reached' in html
        ):
            raise Exception('YouTube upload failed')

        elapsed = time.time() - start

        print(f'Still uploading... {int(elapsed)}s')

        if elapsed > 3600:
            raise Exception('Upload timeout after 1 hour')

        time.sleep(5)


with sync_playwright() as p:

    print('Launching browser...')

    browser = p.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
        ]
    )

    context = browser.new_context()

    print('Loading cookies...')

    cookies = load_cookies()

    formatted = []

    for c in cookies:

        item = {
            'name': c['name'],
            'value': c['value'],
            'domain': c['domain'],
            'path': c.get('path', '/'),
            'secure': c.get('secure', False),
        }

        formatted.append(item)

    context.add_cookies(formatted)

    page = context.new_page()

    print('Opening YouTube Studio...')

    page.goto(
        'https://studio.youtube.com',
        wait_until='networkidle',
        timeout=120000
    )

    time.sleep(5)

    print('Opening upload page...')

    page.goto(
        'https://studio.youtube.com/channel/UC/videos/upload',
        wait_until='networkidle',
        timeout=120000
    )

    time.sleep(5)

    print('Selecting video file...')

    file_input = page.locator('input[type='file']').first
    file_input.set_input_files(VIDEO_FILE)

    print('Video selected.')

    time.sleep(10)

    print('Setting title...')

    title_box = page.locator(
        'div[aria-label*='title']'
    ).first

    title_box.click()

    page.keyboard.press('Control+A')
    page.keyboard.press('Backspace')

    title_box.fill(TITLE)

    print('Setting description...')

    desc_box = page.locator(
        'div[aria-label*='Tell viewers about your video']'
    ).first

    desc_box.click()
    desc_box.fill(DESCRIPTION)

    wait_for_upload(page)

    print('Navigating upload steps...')

    for i in range(3):
        print(f'Next step {i+1}')

        next_btn = page.locator('#next-button').first
        next_btn.click()

        time.sleep(3)

    print(f'Setting visibility: {VISIBILITY}')

    if VISIBILITY.lower() == 'public':
        page.locator(
            'tp-yt-paper-radio-button[name='PUBLIC']'
        ).click()

    elif VISIBILITY.lower() == 'private':
        page.locator(
            'tp-yt-paper-radio-button[name='PRIVATE']'
        ).click()

    else:
        page.locator(
            'tp-yt-paper-radio-button[name='UNLISTED']'
        ).click()

    time.sleep(2)

    print('Finishing upload...')

    done_btn = page.locator('#done-button').first
    done_btn.click()

    time.sleep(10)

    video_url = None

    try:
        print('Trying to extract video URL...')

        view_link = page.locator(
            'a:has-text('View on YouTube')'
        ).first

        href = view_link.get_attribute('href')

        if href:
            video_url = href

    except Exception as e:
        print(f'Could not get URL: {e}')

    print('===================================')

    if video_url:

        print(f'VIDEO_URL={video_url}')

        match = re.search(
            r'(?:v=|youtu\.be/)([A-Za-z0-9_-]+)',
            video_url
        )

        if match:
            print(f'VIDEO_ID={match.group(1)}')

    else:
        print('Upload completed but URL was not detected.')

    print('SUCCESS: upload workflow finished')

    print('===================================')

    browser.close()
