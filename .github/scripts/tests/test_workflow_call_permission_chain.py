"""Reject permission grants that GitHub validates away before any job starts.

A caller workflow's `permissions` block sets the ceiling for everything it
calls. When a job inside a called workflow requests a token scope that the
caller never granted, GitHub rejects the caller file at parse time: the run
becomes a `startup_failure` with zero jobs, no log, and no annotation any API
exposes. actionlint does not model this cross-file rule, so
`.github/workflows/nightly-cua-driver.yml` died that way on every scheduled run
from 2026-10-25 because `staging-gate` in `cd-rust-cua-driver.yml` requests
`statuses: read`.

The check walks every local reusable-workflow call. A job may widen the
`permissions` block of its own workflow (that is an override, not a ceiling),
but it may never exceed the grant passed down by its callers.
"""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / '.github/workflows'

SCOPES = (
    'actions', 'attestations', 'checks', 'contents', 'deployments',
    'discussions', 'id-token', 'issues', 'models', 'packages', 'pages',
    'pull-requests', 'security-events', 'statuses',
)
LEVEL = {'none': 0, 'read': 1, 'write': 2}
# A root workflow is bounded by the repository default, not by a caller.
UNBOUNDED = {scope: 'write' for scope in SCOPES}


def normalize(block):
    if block is None:
        return {}
    if block == 'read-all':
        return {scope: 'read' for scope in SCOPES}
    if block == 'write-all':
        return {scope: 'write' for scope in SCOPES}
    if not isinstance(block, dict):
        return {}
    return {scope: str(level).lower() for scope, level in block.items()}


def narrow(outer, inner):
    """The tighter of two grants for every scope either mentions."""
    merged = {}
    for scope in set(outer) | set(inner):
        granted = outer.get(scope, 'none')
        requested = inner.get(scope, 'none')
        merged[scope] = min((granted, requested), key=lambda level: LEVEL.get(level, 0))
    return merged


def excess(requested, granted):
    return {
        scope: level
        for scope, level in requested.items()
        if level != 'none' and LEVEL.get(granted.get(scope, 'none'), 0) < LEVEL.get(level, 0)
    }


def local_call(target):
    if not str(target or '').startswith('./.github/workflows/'):
        return None
    return str(target).rsplit('/', 1)[-1]


def find_violations(directory):
    """Every (file, job, excess, grant) whose job requests more than its chain grants."""
    directory = Path(directory)
    violations = []

    def walk(name, grant, seen):
        workflow = yaml.safe_load((directory / name).read_text())
        if not isinstance(workflow, dict):
            return
        default = normalize(workflow.get('permissions'))
        for job_id, job in (workflow.get('jobs') or {}).items():
            if not isinstance(job, dict):
                continue
            requested = normalize(job.get('permissions'))
            if job.get('permissions') is None:
                requested = default
            over = excess(requested, grant)
            if over:
                violations.append((name, job_id, over, grant))
            target = local_call(job.get('uses'))
            if target and target not in seen and (directory / target).exists():
                walk(target, narrow(requested, grant), seen | {target})

    for path in sorted(directory.glob('*.yml')):
        if './.github/workflows/' not in path.read_text():
            continue
        walk(path.name, UNBOUNDED, {path.name})
    return violations


def test_repository_call_chains_grant_every_requested_scope():
    violations = find_violations(WORKFLOWS)
    assert not violations, '\n'.join(
        f'{name}: job {job_id} requests {sorted(over)} but the caller chain grants only '
        f'{sorted(scope for scope, level in grant.items() if level != "none")}'
        for name, job_id, over, grant in violations
    )


def test_detects_scope_missing_from_caller(tmp_path):
    (tmp_path / 'callee.yml').write_text(
        'on:\n  workflow_call:\npermissions:\n  contents: read\n'
        'jobs:\n  gate:\n    runs-on: ubuntu-latest\n    permissions:\n'
        '      contents: read\n      statuses: read\n    steps:\n      - run: true\n'
    )
    (tmp_path / 'caller.yml').write_text(
        'on:\n  schedule:\n    - cron: "0 0 * * *"\npermissions:\n  contents: write\n'
        'jobs:\n  build:\n    uses: ./.github/workflows/callee.yml\n'
    )
    violations = find_violations(tmp_path)
    assert [(name, job_id, over) for name, job_id, over, _ in violations] == [
        ('callee.yml', 'gate', {'statuses': 'read'}),
    ]


def test_allows_job_to_widen_its_own_workflow_block_within_caller_grant(tmp_path):
    """A called job may exceed its own workflow block, as long as the caller grants it.

    `cd-image-linux.yml` does exactly this: its workflow block is `contents: read`
    while a job adds `packages: write`. GitHub accepts that, because a job block
    overrides its own workflow default. The ceiling is the caller's grant, so a
    model that also intersected the containing workflow block would reject this.
    """
    (tmp_path / 'callee.yml').write_text(
        'on:\n  workflow_call:\npermissions:\n  contents: read\n'
        'jobs:\n  publish:\n    runs-on: ubuntu-latest\n    permissions:\n'
        '      contents: read\n      statuses: read\n    steps:\n      - run: true\n'
    )
    (tmp_path / 'caller.yml').write_text(
        'on:\n  push:\n    branches: [main]\npermissions:\n'
        '  contents: write\n  statuses: read\n'
        'jobs:\n  build:\n    uses: ./.github/workflows/callee.yml\n'
    )
    assert find_violations(tmp_path) == []


def test_detects_widened_job_when_caller_grant_is_narrower(tmp_path):
    """The same job fails once the caller stops granting the extra scope."""
    (tmp_path / 'callee.yml').write_text(
        'on:\n  workflow_call:\npermissions:\n  contents: read\n'
        'jobs:\n  publish:\n    runs-on: ubuntu-latest\n    permissions:\n'
        '      contents: read\n      statuses: read\n    steps:\n      - run: true\n'
    )
    (tmp_path / 'caller.yml').write_text(
        'on:\n  push:\n    branches: [main]\npermissions:\n  contents: write\n'
        'jobs:\n  build:\n    uses: ./.github/workflows/callee.yml\n'
    )
    violations = find_violations(tmp_path)
    assert [(name, job_id, over) for name, job_id, over, _ in violations] == [
        ('callee.yml', 'publish', {'statuses': 'read'}),
    ]
