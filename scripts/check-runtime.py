#!/usr/bin/env python3
"""Run on the Magnolia instance through SSM; print only sanitized diagnostics."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.request


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(url):
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b''
    except (urllib.error.URLError, TimeoutError):
        return 0, b''


def main():
    evidence = {}
    for service in ('magnolia', 'nginx', 'snap.amazon-ssm-agent.amazon-ssm-agent'):
        _, status, _ = command('systemctl', 'show', service,
                               '--property=ActiveState,SubState,Result,NRestarts,ExecMainStatus,ActiveEnterTimestamp')
        evidence[service] = dict(line.split('=', 1) for line in status.splitlines())
    rc, output, _ = command('cloud-init', 'status', '--format=json')
    cloud = json.loads(output)
    evidence['cloud_init'] = {key: cloud.get(key) for key in ('status', 'extended_status', 'boot_status_code')}
    evidence['cloud_init']['exit_code'] = rc
    bootstrap = Path('/var/log/magnolia-bootstrap.log').read_text()
    evidence['bootstrap'] = {
        'complete': 'Magnolia provisioning complete;' in bootstrap,
        'failure_lines': re.findall(r'Magnolia bootstrap failed at line \d+ \(exit \d+\)', bootstrap),
        'nginx_native_check': 'syntax is ok' in bootstrap and 'test is successful' in bootstrap,
    }
    cloud_output = Path('/var/log/cloud-init-output.log').read_text()
    evidence['cloud_init_output'] = {
        'bootstrap_complete_count': cloud_output.count('Magnolia provisioning complete;'),
        'bootstrap_failed': 'Magnolia bootstrap failed' in cloud_output,
    }
    evidence['nginx_check_exit'] = command('nginx', '-t')[0]
    evidence['unit_check_exit'] = command('systemd-analyze', 'verify', '/etc/systemd/system/magnolia.service')[0]
    _, packages, _ = command('dpkg-query', '-W', '-f=${Package} ${Version}\n',
                             'nginx', 'openjdk-17-jre-headless', 'curl', 'unzip', 'python3')
    evidence['packages'] = packages.splitlines()
    _, java, java_error = command('java', '-version')
    evidence['java_version'] = (java or java_error).splitlines()[:1]
    _, listeners, _ = command('ss', '-lnt')
    evidence['listeners'] = [line.split()[3] for line in listeners.splitlines()[1:]
                             if line.split()[3].endswith((':80', ':8080', ':8005', ':8009'))]
    for port in (80, 8080):
        status, body = http(f'http://127.0.0.1:{port}/magnoliaAuthor/.rest/health/ready')
        evidence[f'readiness_{port}'] = status
        if status == 200:
            health = json.loads(body)
            evidence[f'health_checks_{port}'] = [
                {key: check.get(key) for key in ('name', 'status')}
                for check in health.get('checks', [])
            ]
    code, body = http('http://127.0.0.1/magnoliaAuthor/travel.html')
    evidence['anonymous_sample_content'] = {'status': code, 'bytes': len(body), 'contains_travel': b'travel' in body.lower()}
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            memory[key + '_KiB'] = int(value.split()[0])
    evidence['memory'] = memory
    _, usage, _ = command('systemctl', 'show', 'magnolia', '--property=MemoryCurrent,MemoryPeak,CPUUsageNSec')
    evidence['jvm_cgroup'] = dict(line.split('=', 1) for line in usage.splitlines())
    disk = shutil.disk_usage('/')
    evidence['root_disk_GiB'] = {key: round(value / 2**30, 2) for key, value in zip(('total', 'used', 'free'), disk)}
    _, data_size, _ = command('du', '-sm', '/var/lib/magnolia/repositories')
    evidence['repository_MiB'] = int(data_size.split()[0])
    evidence['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    evidence['uptime_seconds'] = float(Path('/proc/uptime').read_text().split()[0])
    # Inspect logs in memory. Never return arbitrary application or cloud-init lines.
    _, journal, _ = command('journalctl', '-u', 'magnolia', '--no-pager', '-o', 'cat')
    evidence['journal_summary'] = {
        'readiness_pass_count': journal.count('Magnolia readiness check passed.'),
        'server_startup_ms': re.findall(r'Server startup in \[(\d+)\] milliseconds', journal),
        'oom_markers': len(re.findall(r'OutOfMemoryError|oom-kill', journal)),
        'error_line_count': sum(bool(re.search(r'\bERROR\b|\bSEVERE\b', line)) for line in journal.splitlines()),
    }
    code, outbound = http('https://checkip.amazonaws.com')
    value = outbound.decode().strip()
    evidence['nat_egress'] = {'status': code, 'public_ip': value if re.fullmatch(r'[0-9.]+', value) else 'unavailable'}
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
