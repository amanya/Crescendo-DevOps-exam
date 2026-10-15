#!/usr/bin/env python3
"""Compare restricted raw state snapshots and emit only lifecycle identity evidence.

State files must stay in ignored, mode-0600 storage. The canonical digest matches
.github/workflows/terraform-plan.yml; no state attributes or lineage are printed.
"""

import argparse
import hashlib
import json
from pathlib import Path
import stat

ALLOWED = {('', 'aws_instance', 'magnolia', None),
           ('', 'aws_lb_target_group_attachment', 'magnolia', None)}


def read(path):
    assert stat.S_IMODE(path.stat().st_mode) == 0o600, 'State must have mode 0600'
    state = json.loads(path.read_text())
    rows = []
    for resource in state['resources']:
        if resource['mode'] == 'managed':
            for instance in resource['instances']:
                assert not instance.get('deposed'), 'Unexpected deposed instance'
                rows.append([resource.get('module', ''), resource['type'], resource['name'],
                             instance.get('index_key'), instance['attributes']['id']])
    assert len(rows) == len({tuple(row[:4]) for row in rows}), 'Duplicate managed address'
    return state, sorted(rows, key=lambda row: json.dumps(row))


def digest(rows):
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    before, old_rows = read(args.before)
    after, new_rows = read(args.after)
    assert before['lineage'] == after['lineage'], 'State lineage changed'
    assert after['serial'] > before['serial'], 'State serial did not advance'
    old, new = ({tuple(row[:4]): row[4] for row in rows} for rows in [old_rows, new_rows])
    assert old.keys() == new.keys(), 'Managed address set changed'
    changed = {key for key in old if old[key] != new[key]}
    assert changed == ALLOWED, 'Changes must be exactly the instance and target attachment'
    print(json.dumps({'lineage_preserved': True, 'before_serial': before['serial'],
                      'after_serial': after['serial'], 'managed_instances': len(new_rows),
                      'unchanged_identities': len(new_rows) - len(changed),
                      'changed': [{'type': key[1], 'name': key[2], 'before': old[key], 'after': new[key]}
                                  for key in sorted(changed, key=str)],
                      'identities_sha256': digest(new_rows), 'passed': True}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'passed': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
