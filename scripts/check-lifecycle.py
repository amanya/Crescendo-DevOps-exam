#!/usr/bin/env python3
"""Run via approved on-instance SSM against the verified CloudFront HTTPS origin.

Create a disposable CMS page, verify it after reboot, or prove its absence after
replacement. Only allowlisted content evidence is emitted. Credentials, cookies,
response bodies, and exception messages stay in memory on EC2.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import urllib.parse
import uuid

spec = importlib.util.spec_from_file_location('cloudfront', Path(__file__).with_name('check-cloudfront.py'))
cloudfront = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloudfront)
EVIDENCE = {}
NAME = 'p07-lifecycle-20261015'
TITLE = 'P07 lifecycle verification 2026-10-15'
MARKER = 'Created before reboot; intentionally discarded on instance replacement.'
NODE = cloudfront.CONTEXT + '/.rest/nodes/v1/website/travel/' + NAME


def properties(node):
    return {p['name']: p.get('values', []) for p in node.get('properties', [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', help='Exact verified cloudfront_url Terraform output')
    parser.add_argument('phase', choices=['create', 'retained', 'absent'])
    parser.add_argument('--expected-identifier')
    parser.add_argument('--expected-boot-id')
    args = parser.parse_args()
    base = args.base.rstrip('/')
    assert re.fullmatch(r'https://[a-z0-9]+\.cloudfront\.net', base)
    if args.phase != 'create':
        assert args.expected_identifier and args.expected_boot_id
        uuid.UUID(args.expected_identifier)
        uuid.UUID(args.expected_boot_id)
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    EVIDENCE.update(phase=args.phase, origin=base, boot_id=boot_id, node_path='/travel/' + NAME)
    client = cloudfront.Client(base)
    code, _, body = client.request(cloudfront.CONTEXT + '/.rest/health/ready')
    assert code == 200 and json.loads(body)['status'] == 'UP'
    EVIDENCE['readiness'] = code
    code, _, body = client.request(cloudfront.ADMIN)
    assert code == 401
    form = cloudfront.Form()
    form.feed(body.decode())
    assert form.hidden.get('csrf')
    password = Path('/etc/magnolia/superuser-password').read_text().strip()
    form.hidden.update(mgnlUserId='superuser', mgnlUserPSWD=password)
    code, _, _ = client.request(cloudfront.ADMIN, urllib.parse.urlencode(form.hidden).encode(),
                               {'Origin': base, 'Referer': base + cloudfront.ADMIN})
    del password, form, body
    assert code in (302, 303)
    code, _, _ = client.request(cloudfront.ADMIN)
    assert code == 200
    EVIDENCE['authenticated_admincentral'] = True
    try:
        code, _, body = client.request(NODE)
        EVIDENCE['initial_node_status'] = code
        if args.phase == 'create':
            assert code == 404, 'Refuse to overwrite an existing test node'
            # Use the installed Travel page template rather than guessing its ID.
            status, _, sample = client.request(cloudfront.CONTEXT + '/.rest/nodes/v1/website/travel/about?includeMetadata=true')
            assert status == 200
            template = properties(json.loads(sample))['mgnl:template']
            payload = {'name': NAME, 'type': 'mgnl:page', 'path': '/travel/' + NAME,
                       'properties': [{'name': name, 'type': 'String', 'values': values} for name, values in
                                      [('title', [TITLE]), ('abstract', [MARKER]), ('mgnl:template', template)]]}
            code, _, _ = client.request(cloudfront.CONTEXT + '/.rest/nodes/v1/website/travel',
                                        json.dumps(payload).encode(),
                                        {'Content-Type': 'application/json', 'Origin': base,
                                         'Referer': base + cloudfront.ADMIN}, method='PUT')
            EVIDENCE['create_status'] = code
            assert code in (200, 201)
            code, _, body = client.request(NODE)
        if args.phase == 'absent':
            assert code == 404
            EVIDENCE['test_content_absent'] = True
            code, _, sample = client.request(cloudfront.CONTEXT + '/.rest/nodes/v1/website/travel')
            assert code == 200 and json.loads(sample)['name'] == 'travel'
            EVIDENCE['fresh_travel_sample_present'] = True
        else:
            assert code == 200
            node = json.loads(body)
            props = properties(node)
            identifier = node['identifier']
            uuid.UUID(identifier)
            assert node['name'] == NAME and node['path'] == '/travel/' + NAME
            assert props['title'] == [TITLE] and props['abstract'] == [MARKER]
            EVIDENCE.update(identifier=identifier, title=TITLE, marker=MARKER, content_matches=True)
            if args.phase == 'retained':
                assert identifier == args.expected_identifier
                EVIDENCE['same_identifier'] = True
        if args.phase != 'create':
            assert boot_id != args.expected_boot_id
            EVIDENCE['boot_id_changed'] = True
    finally:
        code, _, _ = client.request(cloudfront.ADMIN + '?mgnlLogout=true')
        assert code in (302, 303)
        code, _, _ = client.request(cloudfront.ADMIN)
        assert code == 401
        EVIDENCE['logout_revokes_access'] = True
        client.jar.clear()
    EVIDENCE['passed'] = True
    print(json.dumps(EVIDENCE, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({**EVIDENCE, 'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
