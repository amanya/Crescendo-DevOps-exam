#!/usr/bin/env python3
"""Check P05 without emitting response bodies, credentials, or cookie values.

Anonymous checks can run anywhere. --authenticated is for an explicitly
approved on-instance SSM run only; the password stays in memory on EC2 and
is submitted only to the verified CloudFront HTTPS origin supplied by Terraform.
"""

import argparse
from html.parser import HTMLParser
import http.cookiejar
import json
from pathlib import Path
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

    def request(self, path, data=None, headers=None, method=None):
        assert path.startswith('/') and not path.startswith('//')
        req = urllib.request.Request(self.base + path, data=data, headers=headers or {}, method=method)
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

    def session(self):
        return next((c.value for c in self.jar if c.name == 'JSESSIONID'), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', help='Exact cloudfront_url Terraform output')
    parser.add_argument('--authenticated', action='store_true')
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
        code, _, _ = client.request('/p05-not-found')
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
    if args.authenticated:
        authenticated(client, form)
    EVIDENCE['passed'] = True
    print(json.dumps(EVIDENCE, indent=2))


def authenticated(client, form):
    password = Path('/etc/magnolia/superuser-password').read_text().strip()
    before = client.session()
    # A missing/wrong CSRF token must not establish an authenticated session.
    invalid = {**form.hidden, 'csrf': 'p05-invalid', 'mgnlUserId': 'superuser', 'mgnlUserPSWD': password}
    code, _, _ = client.request(ADMIN, urllib.parse.urlencode(invalid).encode(),
                               {'Origin': client.base, 'Referer': client.base + ADMIN})
    assert code in (400, 401, 403)
    EVIDENCE['invalid_csrf_rejected'] = True
    code, _, body = client.request(ADMIN)
    assert code == 401
    form = Form()
    form.feed(body.decode())
    form.hidden.update(mgnlUserId='superuser', mgnlUserPSWD=password)
    code, _, _ = client.request(ADMIN, urllib.parse.urlencode(form.hidden).encode(),
                               {'Origin': client.base, 'Referer': client.base + ADMIN})
    del password, invalid, form
    assert code in (302, 303)
    EVIDENCE['login_status'] = code
    session = client.session()
    assert session and session != before
    EVIDENCE['session_created_or_rotated'] = True
    attrs = [dict(path=c.path, secure=c.secure, http_only=c.has_nonstandard_attr('HttpOnly'))
             for c in client.jar if c.name == 'JSESSIONID']
    assert attrs and all(c['secure'] and c['http_only'] and c['path'] == CONTEXT for c in attrs)
    EVIDENCE['session_cookie_attributes'] = attrs
    for path in [ADMIN, CONTEXT + '/travel.html', CONTEXT + '/.rest/nodes/v1/website/travel',
                 CONTEXT + '/.rest/nodes/v1/config/modules?depth=1']:
        code, _, body = client.request(path)
        assert code == 200
        assert client.session() == session
        assert b'.elb.amazonaws.com' not in body
        if path.endswith('travel.html'):
            assert b'travel' in body.lower()
            assets = sorted({urllib.parse.urlsplit(p).path for p in
                re.findall(r'(?:href|src)=[\"\']([^\"\']+)', body.decode())
                if p.startswith(CONTEXT + '/.resources/') and re.search(r'\.(css|js|svg|png|jpg)$', p)})[:6]
            assert len(assets) >= 3
            for asset in assets:
                code, _, content = client.request(asset)
                assert code == 200 and content
            EVIDENCE['sample_assets_checked'] = len(assets)
        if 'depth=1' in path:
            assert len(json.loads(body).get('nodes', [])) > 20
    EVIDENCE['admin_sample_content_query_and_session_reuse'] = True
    # Independent clients request the exact authenticated URLs, without a cache
    # buster. They must receive their own login/session, never another user's.
    for _ in range(3):
        anonymous = Client(client.base)
        for path in [ADMIN, CONTEXT + '/travel.html', CONTEXT + '/.rest/nodes/v1/website/travel']:
            code, _, _ = anonymous.request(path)
            assert code == 401 and anonymous.session() != session
    EVIDENCE['anonymous_session_isolation'] = True
    code, _, _ = client.request(ADMIN + '?mgnlLogout=true')
    assert code in (302, 303)
    code, _, _ = client.request(ADMIN)
    assert code == 401
    EVIDENCE['logout_revokes_access'] = True


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({**EVIDENCE, 'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
