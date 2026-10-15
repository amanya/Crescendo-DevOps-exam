#!/usr/bin/env python3
"""Check login through SSM and loopback only; never print credentials or cookies.

P04 explicitly authorizes the local-file exception to the Secrets Manager rule.
Run as root on the instance. No arguments or environment secret inputs are used.
"""

from html.parser import HTMLParser
import http.cookiejar
import json
from pathlib import Path
import re
import stat
import urllib.error
import urllib.parse
import urllib.request


BASE = 'http://127.0.0.1/magnoliaAuthor'
EVIDENCE = {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden' and attrs.get('name'):
            self.hidden[attrs['name']] = attrs.get('value', '')


def main():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPCookieProcessor(jar), NoRedirect)

    def request(path, data=None):
        # Paths are local constants or validated application assets. Never follow
        # redirects, and never include credentials in URLs, argv, or output.
        assert path.startswith('/') and not path.startswith('//')
        req = urllib.request.Request(BASE + path, data=data)
        try:
            response = opener.open(req, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read()

    evidence = EVIDENCE
    admin = '/.magnolia/admincentral'
    code, _, body = request(admin)
    evidence['anonymous_admin_status'] = code
    assert code == 401
    form = LoginForm()
    form.feed(body.decode())
    assert 'csrf' in form.hidden
    before = {cookie.name: cookie.value for cookie in jar}
    path = Path('/etc/magnolia/superuser-password')
    evidence['password_file_mode'] = oct(stat.S_IMODE(path.stat().st_mode))
    form.hidden.update(mgnlUserId='superuser', mgnlUserPSWD=path.read_text().strip())
    payload = urllib.parse.urlencode(form.hidden).encode()
    code, headers, _ = request(admin, payload)
    del payload, form
    evidence['login_status'] = code
    assert code in (200, 302, 303)
    after = {cookie.name: cookie.value for cookie in jar}
    evidence['session_rotated'] = before.get('JSESSIONID') != after.get('JSESSIONID')
    assert after.get('JSESSIONID') and evidence['session_rotated']
    evidence['session_cookie'] = [
        {'path': cookie.path, 'secure': cookie.secure,
         'http_only': cookie.has_nonstandard_attr('HttpOnly')}
        for cookie in jar if cookie.name == 'JSESSIONID'
    ]
    assert all(cookie['http_only'] and cookie['path'] == '/magnoliaAuthor'
               for cookie in evidence['session_cookie'])
    code, _, body = request('/.rest/nodes/v1/website/travel')
    evidence['authenticated_content_api_status'] = code
    assert code == 200
    node = json.loads(body)
    evidence['sample_node_is_travel'] = node.get('name') == 'travel'
    assert evidence['sample_node_is_travel'] and node.get('identifier')
    code, _, body = request('/travel.html')
    evidence['sample_page_status'] = code
    evidence['sample_page_bytes'] = len(body)
    evidence['sample_page_contains_travel'] = b'travel' in body.lower()
    assert code == 200 and evidence['sample_page_contains_travel']
    # Check assets referenced by the initialized page, without returning HTML.
    paths = re.findall(r'(?:href|src)=[\"\']([^\"\']+)', body.decode())
    assets = sorted({urllib.parse.urlsplit(value).path for value in paths
                     if value.startswith('/magnoliaAuthor/.resources/')
                     and re.search(r'\.(css|js|svg|png|jpg)$', value)})[:6]
    assert len(assets) >= 3
    evidence['sample_assets'] = []
    for asset in assets:
        code, _, content = request(asset.removeprefix('/magnoliaAuthor'))
        evidence['sample_assets'].append({'path': asset, 'status': code, 'bytes': len(content)})
        assert code == 200 and content
    code, _, body = request('/.rest/nodes/v1/config/modules?depth=1')
    evidence['installed_modules_status'] = code
    assert code == 200
    modules = json.loads(body)
    evidence['installed_module_count'] = len(modules.get('nodes', []))
    assert evidence['installed_module_count'] > 20
    code, _, body = request(admin)
    evidence['session_admin_status'] = code
    evidence['session_admin_bytes'] = len(body)
    assert code == 200
    # Only compare stable identifiers locally; do not emit cookie values, account
    # records, repository payloads, or password-derived hashes.
    baseline = Path('/var/lib/magnolia/.p04-baseline.json')
    current = {'sample_id': node.get('identifier'), 'repository_inode': Path('/var/lib/magnolia/repositories').stat().st_ino,
               'password_inode': path.stat().st_ino}
    if baseline.exists():
        evidence['existing_data_and_file_reused'] = json.loads(baseline.read_text()) == current
        assert evidence['existing_data_and_file_reused']
    else:
        baseline.write_text(json.dumps(current))
        baseline.chmod(0o600)
        evidence['baseline_recorded'] = True
    code, _, _ = request('/.magnolia/admincentral?mgnlLogout=true')
    evidence['logout_status'] = code
    code, _, _ = request(admin)
    evidence['after_logout_admin_status'] = code
    assert code == 401
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Exception messages and tracebacks can contain request data. Return only
        # the class; diagnose with targeted, sanitized probes when needed.
        print(json.dumps({**EVIDENCE, 'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
