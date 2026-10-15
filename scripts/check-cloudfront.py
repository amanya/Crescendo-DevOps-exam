#!/usr/bin/env python3
"""Check readiness, redirects, caching, and login assets without signing in.

Print check results without response bodies or cookie values.
"""

import argparse
from html.parser import HTMLParser
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request

EVIDENCE = {}
CONTEXT = '/magnoliaAuthor'
ADMIN = CONTEXT + '/.magnolia/admincentral'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden' and attrs.get('name'):
            self.hidden[attrs['name']] = attrs.get('value', '')


class Client:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    def request(self, path, headers=None):
        assert path.startswith('/') and not path.startswith('//')
        req = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            response = self.opener.open(req, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            location = response.headers.get('Location')
            if location:
                target = urllib.parse.urlsplit(urllib.parse.urljoin(self.base + path, location))
                assert target.scheme == 'https' and target.netloc == urllib.parse.urlsplit(self.base).netloc
            assert response.headers.get('Age') in (None, '0')
            assert 'Hit' not in response.headers.get('X-Cache', '')
            assert 'no-store' in response.headers.get('Cache-Control', '')
            return response.code, response.headers, body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', help='Exact cloudfront_url Terraform output')
    args = parser.parse_args()
    base = args.base.rstrip('/')
    assert re.fullmatch(r'https://[a-z0-9]+\.cloudfront\.net', base)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    try:
        response = opener.open(base.replace('https://', 'http://') + '/', timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.code == 301 and response.headers['Location'] == base + '/'
    EVIDENCE['viewer_http_redirects_to_https'] = True
    client = Client(base)
    for path in ['/', CONTEXT]:
        code, headers, _ = client.request(path)
        assert code == 302 and headers['Location'] == CONTEXT + '/'
    EVIDENCE['relative_root_context_redirects'] = True
    code, _, body = client.request(CONTEXT + '/.rest/health/ready')
    health = json.loads(body)
    assert code == 200 and health['status'] == 'UP'
    EVIDENCE['readiness_status'] = code
    for _ in range(2):
        code, _, _ = client.request('/magnolia-check-not-found')
        assert code == 404
    EVIDENCE['uncached_404_status_preserved'] = True
    code, _, body = client.request(ADMIN)
    assert code == 401 and b'mgnlUserPSWD' in body
    form = Form()
    form.feed(body.decode())
    assert form.hidden.get('csrf')
    EVIDENCE['csrf_form_present'] = True
    EVIDENCE['anonymous_login_status'] = code
    attrs = [dict(path=c.path, secure=c.secure, http_only=c.has_nonstandard_attr('HttpOnly'))
             for c in client.jar if c.name == 'csrf']
    assert attrs and all(c['secure'] and c['http_only'] and c['path'] == CONTEXT for c in attrs)
    EVIDENCE['csrf_cookie_attributes'] = attrs
    spoofed = Client(base)
    code, _, _ = spoofed.request(ADMIN, headers={
        'X-Forwarded-Proto': 'http', 'CloudFront-Forwarded-Proto': 'http'})
    assert code == 401
    csrf = [c for c in spoofed.jar if c.name == 'csrf']
    assert csrf and all(c.secure for c in csrf)
    EVIDENCE['viewer_protocol_spoof_does_not_downgrade_cookie'] = True
    # Referenced login assets must resolve on the public HTTPS origin.
    assets = sorted({urllib.parse.urljoin(base + ADMIN, p) for p in
        re.findall(r'(?:href|src)=[\"\']([^\"\']+)', body.decode())
        if re.search(r'\.(css|js|svg|png|jpg)(?:\?|$)', p)})
    EVIDENCE['login_assets_checked'] = 0
    for asset in assets:
        target = urllib.parse.urlsplit(asset)
        assert target.scheme == 'https' and target.netloc == urllib.parse.urlsplit(base).netloc
        code, _, content = client.request(target.path + ('?' + target.query if target.query else ''))
        assert code == 200 and content
        EVIDENCE['login_assets_checked'] += 1
    assert EVIDENCE['login_assets_checked'] >= 3
    EVIDENCE['passed'] = True
    print(json.dumps(EVIDENCE, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({**EVIDENCE, 'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
