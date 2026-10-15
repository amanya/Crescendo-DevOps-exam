#!/usr/bin/env python3
"""Render application templates with Terraform and check syntax without running the bootstrap."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Also verify a downloaded CE bundle')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    templates = root / 'infra/templates'
    output = root / 'build/provisioning'
    output.mkdir(parents=True, exist_ok=True)
    service = f'templatefile({json.dumps(str(templates / "magnolia.service.tftpl"))}, {{}})'
    nginx = f'templatefile({json.dumps(str(templates / "nginx.conf.tftpl"))}, {{}})'
    bootstrap = (
        f'templatefile({json.dumps(str(templates / "bootstrap.sh.tftpl"))}, '
        f'{{magnolia_service_b64=base64encode({service}), nginx_config_b64=base64encode({nginx})}})'
    )
    expression = f'jsonencode({{bootstrap={bootstrap}, service={service}, nginx={nginx}}})'
    # No provider configuration, AWS credentials, or state from infra is needed.
    with tempfile.TemporaryDirectory(prefix='crescendo-provisioning-') as work:
        result = subprocess.run(['terraform', 'console', '-no-color'], cwd=work,
                                input=expression + '\n', text=True, capture_output=True, check=True)
    rendered = json.loads(json.loads(result.stdout))
    paths = {'bootstrap': 'bootstrap.sh', 'service': 'magnolia.service', 'nginx': 'nginx.conf'}
    for key, name in paths.items():
        (output / name).write_text(rendered[key])
    subprocess.run(['bash', '-n', str(output / 'bootstrap.sh')], check=True)
    # Extract generated shell scripts and check those as well.
    for delimiter, name in [('SETENV', 'setenv.sh'), ('READY', 'magnolia-ready')]:
        content = rendered['bootstrap'].split(f"<<'{delimiter}'\n", 1)[1].split(f'\n{delimiter}\n', 1)[0]
        (output / name).write_text(content + '\n')
        subprocess.run(['bash', '-n', str(output / name)], check=True)
    for index, content in enumerate(rendered['bootstrap'].split("<<'PY'\n")[1:]):
        compile(content.split('\nPY\n', 1)[0], f'bootstrap-python-{index}', 'exec')
    assert len(rendered['bootstrap'].encode()) < 16384, 'EC2 raw user data exceeds 16 KiB'
    assert '%{http_code}' in rendered['bootstrap'], 'curl format was not preserved'
    if shutil.which('shellcheck'):
        subprocess.run(['shellcheck', '-e', 'SC1091', str(output / 'bootstrap.sh'),
                        str(output / 'magnolia-ready')], check=True)
    else:
        print('shellcheck unavailable; bash syntax and embedded Python compilation checked.')
    print(f'Terraform rendered all three templates; shell syntax passed; user data is {len(rendered["bootstrap"].encode())} bytes.')
    if args.archive:
        verify_archive(args.archive, rendered['bootstrap'])
    print(f'Rendered files: {output}')


def verify_archive(path, bootstrap):
    expected = '8ba8ea6bcaffb7c6f6895d2ed024e322bfed546f6e475c710018b7a3b16b1a99'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Bundle checksum mismatch'
    prefix = 'travel-demo-community-webapp-6.3.27/apache-tomcat-9.0.121/'
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, 'ZIP integrity check failed'
        assert prefix + 'webapps/magnoliaAuthor/WEB-INF/lib/magnolia-core-6.3.27.jar' in archive.namelist()
        with zipfile.ZipFile(io.BytesIO(archive.read(prefix + 'lib/catalina.jar'))) as jar:
            assert b'server.info=Apache Tomcat/9.0.121' in jar.read('org/apache/catalina/util/ServerInfo.properties')
        persistence = archive.read(prefix + 'webapps/magnoliaAuthor/WEB-INF/config/repo-conf/jackrabbit-bundle-h2-search.xml')
        assert b'H2PersistenceManager' in persistence and b'FileDataStore' in persistence
        # Apply the real configuration transform to an isolated copy. This checks
        # paths and XML assertions against the selected archive without starting Java.
        with tempfile.TemporaryDirectory(prefix='crescendo-provisioning-archive-') as work:
            app = Path(work)
            for relative in ['conf/server.xml', 'webapps/magnoliaAuthor/WEB-INF/config/default/magnolia.properties']:
                target = app / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(prefix + relative))
            transform = bootstrap.split("<<'PY'\n")[2].split('\nPY\n', 1)[0]
            transform = transform.replace('/opt/magnolia/', str(app) + '/')
            subprocess.run(['python3', '-c', transform], check=True)
            once = [(p, p.read_bytes()) for p in app.rglob('*') if p.is_file()]
            subprocess.run(['python3', '-c', transform], check=True)
            assert all(p.read_bytes() == value for p, value in once), 'Transform is not repeatable'
            import xml.etree.ElementTree as ET
            server = ET.parse(app / 'conf/server.xml').getroot()
            assert server.get('port') == '-1'
            assert server.find('./Service/Connector').get('address') == '127.0.0.1'
    print('Archive checksum, ZIP integrity, Magnolia/Tomcat versions, embedded persistence, and repeated configuration transform passed.')


if __name__ == '__main__':
    main()
