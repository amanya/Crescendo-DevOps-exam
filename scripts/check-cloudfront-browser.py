#!/usr/bin/env python3
"""Run the approved P05 browser checks on EC2; emit sanitized evidence only.

Requires Playwright/Chromium as temporary test tooling. Do not enable tracing,
video, HAR, request logging, persistent browser profiles, or storage-state export.
The local password and cookies stay in memory on the instance. All browser
requests are restricted to the verified CloudFront HTTPS origin.
"""

import argparse
import json
from pathlib import Path
import re
import urllib.parse

from playwright.sync_api import sync_playwright

EVIDENCE = {}
CONTEXT = '/magnoliaAuthor'
ADMIN = CONTEXT + '/.magnolia/admincentral'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', help='Exact cloudfront_url Terraform output')
    parser.add_argument('--screenshot-dir', type=Path)
    args = parser.parse_args()
    base = args.base.rstrip('/')
    assert re.fullmatch(r'https://[a-z0-9]+\.cloudfront\.net', base)
    host = urllib.parse.urlsplit(base).netloc
    EVIDENCE.update(blocked_requests=0, blocked_destinations=[], unexpected_blocked_requests=0,
                    mixed_content_errors=0, page_errors=0)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1000, 'height': 750})

        def restrict(route):
            url = urllib.parse.urlsplit(route.request.url)
            if url.scheme == 'https' and url.netloc == host:
                route.continue_()
            else:
                EVIDENCE['blocked_requests'] += 1
                destination = url.scheme + '://' + url.netloc
                # These optional Travel-demo fonts/widgets stay outside the
                # approved credential test destination. A downgrade, different
                # navigation target, or new external dependency must fail.
                optional_assets = {'https://fonts.googleapis.com', 'https://cdn.jsdelivr.net',
                                   'https://static.addtoany.com'}
                if destination not in optional_assets or route.request.is_navigation_request():
                    EVIDENCE['unexpected_blocked_requests'] += 1
                if destination not in EVIDENCE['blocked_destinations']:
                    EVIDENCE['blocked_destinations'].append(destination)
                route.abort()

        context.route('**/*', restrict)
        page = context.new_page()
        page.on('console', lambda message: EVIDENCE.update(
            mixed_content_errors=EVIDENCE['mixed_content_errors'] +
            int('mixed content' in message.text.lower())))
        page.on('pageerror', lambda _: EVIDENCE.update(page_errors=EVIDENCE['page_errors'] + 1))
        navigations = []
        page.on('request', lambda request: navigations.append(request.url)
                if request.is_navigation_request() else None)

        def public_page():
            target = urllib.parse.urlsplit(page.url)
            assert target.scheme == 'https' and target.netloc == host
            assert page.locator('[src^="http:"],link[href^="http:"],form[action^="http:"]').count() == 0
            assert page.locator('[src*=".elb.amazonaws.com"],[href*=".elb.amazonaws.com"]').count() == 0

        def admin_ready():
            page.wait_for_function("document.body.innerText.includes('Pages') && document.body.innerText.includes('Assets')",
                                   timeout=120000)
            assert page.locator('input[type="password"]').count() == 0
            public_page()

        response = page.goto(base + ADMIN, wait_until='domcontentloaded', timeout=120000)
        assert response.status == 401
        assert page.locator('input[name="mgnlUserId"]').is_visible()
        public_page()
        # Check the form target before loading the credential into the browser.
        action = page.locator('form').first.get_attribute('action') or page.url
        target = urllib.parse.urlsplit(urllib.parse.urljoin(page.url, action))
        assert target.scheme == 'https' and target.netloc == host
        page.locator('input[name="mgnlUserId"]').fill('superuser')
        password = Path('/etc/magnolia/superuser-password').read_text().strip()
        page.locator('input[name="mgnlUserPSWD"]').fill(password)
        del password
        with page.expect_navigation(wait_until='domcontentloaded', timeout=120000):
            page.get_by_role('button', name='Login', exact=True).click()
        admin_ready()
        EVIDENCE['admincentral_pages_and_assets_rendered'] = True
        cookies = [c for c in context.cookies() if c['name'] == 'JSESSIONID']
        assert len(cookies) == 1
        cookie = cookies[0]
        session = cookie['value']
        assert cookie['secure'] and cookie['httpOnly'] and cookie['path'] == CONTEXT
        EVIDENCE['session_cookie'] = {k: cookie[k] for k in ['secure', 'httpOnly', 'path', 'sameSite']}
        del cookies, cookie
        if args.screenshot_dir:
            args.screenshot_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Let Magnolia's entrance transition finish before capturing evidence.
            page.wait_for_timeout(1500)
            page.screenshot(path=str(args.screenshot_dir / 'admincentral.jpg'), type='jpeg', quality=65, animations='disabled')
        response = page.goto(base + CONTEXT + '/travel.html', wait_until='domcontentloaded', timeout=120000)
        assert response.status == 200 and 'travel' in page.locator('body').inner_text().lower()
        public_page()
        assert page.locator('img').count() > 0
        page.wait_for_function('Array.from(document.images).some(image => image.complete && image.naturalWidth > 0)', timeout=30000)
        EVIDENCE['sample_page_and_images_rendered'] = True
        if args.screenshot_dir:
            page.screenshot(path=str(args.screenshot_dir / 'travel.jpg'), type='jpeg', quality=30)
        page.goto(base + ADMIN, wait_until='domcontentloaded', timeout=120000)
        admin_ready()
        page.reload(wait_until='domcontentloaded', timeout=120000)
        admin_ready()
        assert next(c['value'] for c in context.cookies() if c['name'] == 'JSESSIONID') == session
        EVIDENCE['session_reused_after_navigation_and_reload'] = True
        anonymous = browser.new_context(viewport={'width': 1000, 'height': 750})
        anonymous.route('**/*', restrict)
        other_page = anonymous.new_page()
        response = other_page.goto(base + ADMIN, wait_until='domcontentloaded', timeout=120000)
        assert response.status == 401 and other_page.locator('input[type="password"]').is_visible()
        assert all(c['value'] != session for c in anonymous.cookies() if c['name'] == 'JSESSIONID')
        EVIDENCE['separate_browser_context_stays_anonymous'] = True
        anonymous.close()
        response = page.goto(base + ADMIN + '?mgnlLogout=true', wait_until='domcontentloaded', timeout=120000)
        assert response.status == 401 and page.locator('input[type="password"]').is_visible()
        public_page()
        response = page.goto(base + ADMIN, wait_until='domcontentloaded', timeout=120000)
        assert response.status == 401
        EVIDENCE['logout_and_subsequent_access_return_login'] = True
        assert all(urllib.parse.urlsplit(url).scheme == 'https' and
                   urllib.parse.urlsplit(url).netloc == host for url in navigations)
        EVIDENCE['all_document_navigation_stayed_on_cloudfront_https'] = True
        assert EVIDENCE['mixed_content_errors'] == 0 and EVIDENCE['page_errors'] == 0
        assert EVIDENCE['unexpected_blocked_requests'] == 0
        context.close()
        browser.close()
    EVIDENCE['passed'] = True
    print(json.dumps(EVIDENCE, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Playwright exceptions/tracebacks can include DOM, form values, or URLs.
        print(json.dumps({**EVIDENCE, 'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
