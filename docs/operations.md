# Setup and operations

## Prerequisites

Use Terraform `~> 1.16.6`, AWS CLI v2, Git, and Python 3. ShellCheck is optional for the provisioning checker. The committed lock files select the AWS provider within `~> 6.69.0`.

Local operations use AWS profile `default` in `eu-central-1`. The provider and backend enforce account `317399646022`. Keep AWS configuration outside the repository. Terraform initialization needs access to the Terraform Registry and provider downloads; provisioning needs Ubuntu repositories and Magnolia's download server.

The configuration targets this existing environment. Before deploying elsewhere, review the account guards, bucket name, AMI availability, repository identity, and OIDC trust in both Terraform roots. The workload needs capacity for a VPC, four subnets, one NAT Gateway and Elastic IP, an ALB, and a 2-vCPU instance. Planning does not verify deployment permissions or capacity.

## Backend bootstrap

The existing workload already uses remote state. Do not repeat its migration or overwrite it with an older local snapshot.

| Setting | Value |
| --- | --- |
| State bucket | `crescendo-exam-tfstate-317399646022-eu-central-1` |
| Workload key | `workload/terraform.tfstate` |
| Native lock key | `workload/terraform.tfstate.tflock` |
| Bootstrap recovery key | `bootstrap/terraform.tfstate` |
| Planning role | `arn:aws:iam::317399646022:role/crescendo-exam-github-plan` |

For a new environment, create the backend first, after reviewing the environment-specific configuration:

```sh
umask 077
mkdir -p build/operations
chmod 700 build/operations
AWS_PROFILE=default terraform -chdir=bootstrap init -input=false -lockfile=readonly
terraform -chdir=bootstrap fmt -check
terraform -chdir=bootstrap validate
AWS_PROFILE=default terraform -chdir=bootstrap plan -out=../build/operations/bootstrap.tfplan
# Review the saved plan before applying.
AWS_PROFILE=default terraform -chdir=bootstrap apply ../build/operations/bootstrap.tfplan
chmod 600 bootstrap/terraform.tfstate
```

The bootstrap uses local state to avoid depending on the bucket it creates. Preserve its state after every apply in restricted local storage and at the bootstrap recovery key. Keep an independent copy outside the checkout and bucket before deleting either. Serialize bootstrap changes manually. If the account already has a GitHub OIDC provider, inspect and import it before applying; do not create a duplicate or delete a shared provider.

## Plan and deploy

Run from the repository root:

```sh
umask 077
mkdir -p build/operations
chmod 700 build/operations
AWS_PROFILE=default terraform -chdir=infra init -input=false -lockfile=readonly
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
python3 scripts/check-provisioning.py
AWS_PROFILE=default terraform -chdir=infra plan -input=false -out=../build/operations/deploy.tfplan
terraform -chdir=infra show ../build/operations/deploy.tfplan
```

Review the saved plan privately, especially instance replacement, disk deletion, routing, security groups, and user data. Apply the exact reviewed file:

```sh
AWS_PROFILE=default terraform -chdir=infra apply ../build/operations/deploy.tfplan
terraform -chdir=infra output
```

The configuration requires no variable file. `ubuntu_ami_name` selects the reviewed Ubuntu image release. AMI or user-data changes can replace the instance and delete CMS content. Commit both provider lock files after intentional dependency updates. State, plans, local variables, and generated diagnostics remain ignored; keep restricted directories at mode `0700`, files at `0600`, and review files before committing.

## Application checks

A successful apply does not confirm application readiness. Initial startup can take several minutes, especially with standard CPU credits. Use the `author_url` and `readiness_url` Terraform outputs. Readiness must return exact HTTP 200; the unauthenticated author login form returns HTTP 401 by design. Use the CloudFront HTTPS URL for browser access.

```sh
python3 scripts/check-cloudfront.py "$(terraform -chdir=infra output -raw cloudfront_url)"
```

The local provisioning checker renders templates and checks syntax without installing the application. Its optional `--archive` argument verifies the downloaded bundle's checksum, integrity, versions, and configuration edits.

Runtime and authenticated helpers run on EC2 through an authorized private Systems Manager session. Keep authentication material on the instance and use only loopback or the verified CloudFront HTTPS destination. Do not export credentials, cookies, response HTML, or raw application logs. The browser helper needs temporary Playwright/Chromium tooling on the instance. It checks the application origin; optional external demo fonts and widgets are blocked and unverified.

## Lifecycle and troubleshooting

Reboot retains content. Instance replacement deletes the root disk and rebuilds a fresh CMS. The lifecycle helper supports `create`, `retained`, and `absent` checks; choose a new test-node name for each repeat. Wait for readiness and ALB target health before each phase. See [recorded lifecycle evidence](submission.md#lifecycle-evidence).

Before a replacement, preserve restricted state snapshots, generate a saved plan with `-replace=aws_instance.magnolia`, and inspect it. The expected replacements are the instance and its target attachment. After applying, compare the snapshots using `scripts/check-state-identities.py`, confirm the old root volume is gone, and verify fresh content through the unchanged CloudFront URL.

Use Systems Manager to inspect cloud-init completion, Magnolia/Nginx service states, local readiness, and ALB health. `scripts/check-runtime.py` returns sanitized summaries. Diagnostic sources include `/var/log/cloud-init-output.log`, `/var/log/magnolia-bootstrap.log`, `journalctl -u magnolia`, `/var/log/magnolia/`, `/opt/magnolia/logs/`, and `/var/log/nginx/magnolia-error.log`.

During startup, CloudFront may return 502/503/504 while the target is unhealthy. The service allows 1,500 seconds for startup. After correcting a failure, reset a reached restart limit with `systemctl reset-failed magnolia`, then restart Magnolia and Nginx. ALB health follows its thresholds, and a sole unhealthy target can still receive requests.

## CI configuration

Configure these nonsecret GitHub Actions repository variables:

| Variable | Purpose |
| --- | --- |
| `AWS_PLAN_ROLE_ARN` | Bootstrap planning-role ARN |
| `TF_STATE_LINEAGE` | Expected workload state lineage |
| `TF_STATE_IDENTITIES_SHA256` | Digest of the verified managed-resource identities |

After an authorized deployment changes resource identities, verify the state and update the identity digest before expecting PR plans to pass. The comparison helper and reusable workflow implement the canonical digest algorithm. Never place whole state in a repository variable. If CloudFront identities change, review the bootstrap policy's specific read ARNs too.

Neither the provider nor backend hardcodes a profile. Set `AWS_PROFILE=default` locally; GitHub Actions uses temporary OIDC environment credentials. The repository customizes its OIDC subject to include repository ID, owner ID, pull-request context, and the reusable workflow reference. Repository moves or trust/workflow changes require a corresponding IAM review.

CI serializes plans and waits up to five minutes for the native S3 lock. Exit 0 means no changes; exit 2 means a successful plan with changes. Other exits fail. Detailed plans and state stay in restricted temporary storage and are not published as artifacts or comments.

## State recovery

Stop CI and manual writers before recovery. Preserve the current S3 version and a restricted local state pull. Retrieve a chosen prior version without printing it, then compare lineage, serial, identities, and live resources before using Terraform's recovery commands. State recovery does not restore CMS content. Remove a stale lock with `terraform -chdir=infra force-unlock LOCK_ID` only after confirming its writer has stopped.

For bootstrap recovery, restore its state from the versioned recovery key or independent backup under `umask 077`. Initialize and validate `bootstrap/`, then verify that its eight existing resources are recognized and the plan is empty before applying. If all bootstrap state copies are lost, import existing resources with provider-documented IDs before applying.

## Teardown

The stack remains running and billable. EC2, EBS, NAT, ALB, public IPv4, CloudFront, and S3 can incur charges. When teardown is authorized:

1. Disable PR planning and stop Terraform writers. Preserve both state snapshots and any needed CMS content outside the resources being removed.
2. With `AWS_PROFILE=default`, review `terraform -chdir=infra plan -destroy`, then destroy the workload while its S3 backend and locking remain available. Instance termination deletes CMS data.
3. Preserve final workload and bootstrap state outside the bucket. Remove the CI role/policy; remove the OIDC provider only if no other roles use it.
4. Review a bootstrap teardown that deliberately removes bucket `prevent_destroy`. Remove retained object versions and delete markers only after saving recovery copies. `force_destroy = false` blocks deletion of a nonempty bucket. Destroy remaining bootstrap resources last.
