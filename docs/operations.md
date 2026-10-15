# Operations

These procedures apply to the existing deployment in AWS account `317399646022`, region `eu-central-1`.

## Prerequisites

Use Terraform 1.16.6, AWS CLI v2, Git, and Python 3, with AWS access configured through profile `default`. The Terraform version constraint also accepts later 1.16 patch releases. No Terraform variable file is required.

Run the commands below from the repository root. Set the AWS profile for the current terminal session:

```sh
export AWS_PROFILE=default
```

## Plan and deploy

Terraform compares the configuration in `infra/` with the existing AWS resources. A plan previews changes; applying the saved plan carries them out. GitHub Actions checks pull requests but does not deploy them.

Prepare a private directory for saved plans, initialize Terraform, and check the configuration:

```sh
umask 077
mkdir -p build/operations
chmod 700 build/operations
terraform -chdir=infra init -input=false -lockfile=readonly
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
python3 scripts/check-provisioning.py
```

`init` downloads the providers and connects to the existing state bucket. It does not create infrastructure. `fmt` and `validate` check the Terraform files; the Python checker checks the application setup templates. Keep the committed provider lock files so these commands use the selected provider versions.

Create and inspect a plan:

```sh
terraform -chdir=infra plan -out=../build/operations/deploy.tfplan
terraform -chdir=infra show ../build/operations/deploy.tfplan
```

Check the proposed additions, changes, and deletions before continuing. Pay particular attention to instance replacement: changing the Ubuntu image (`ubuntu_ami_name`) or startup configuration can replace the instance and delete all CMS content.

Apply the saved plan once you have reviewed it:

```sh
terraform -chdir=infra apply ../build/operations/deploy.tfplan
terraform -chdir=infra output
```

Keep state and saved plans private and out of Git; they can contain sensitive data. If you change the configuration after planning, create and review a new plan before applying.

## Application checks

Installation continues on the instance after Terraform finishes. Allow several minutes, then run:

```sh
python3 scripts/check-cloudfront.py "$(terraform -chdir=infra output -raw cloudfront_url)"
```

The checker runs without signing in and verifies readiness, redirects, caching, login-page assets, and cookie attributes through CloudFront. It needs only Python 3 and the public URL. Readiness must return HTTP 200. The login page returns HTTP 401 before authentication by design.

Open the `author_url` Terraform output in a browser to use Magnolia. Always use the CloudFront HTTPS address. See the [README](../README.md#how-to-run) for login instructions and [recorded test results](submission.md#lifecycle-evidence) for the reboot and replacement checks.

## Lifecycle and troubleshooting

Rebooting retains CMS content. Replacing or terminating the instance deletes its root disk. A replacement automatically installs a fresh Magnolia instance. There are no CMS backups, so preserve any content you need before replacing the instance.

Use AWS Systems Manager to access the private instance. Its ID is available through `terraform -chdir=infra output -raw instance_id`. CLI sessions require the Session Manager plugin.

If the application is unavailable, check the following on the instance:

| Check | Command or location |
| --- | --- |
| Initial installation | `cloud-init status --long` and `/var/log/magnolia-bootstrap.log` |
| Services | `systemctl status magnolia nginx` |
| Magnolia process logs | `journalctl -u magnolia` |
| Application logs | `/var/log/magnolia/` and `/opt/magnolia/logs/` |
| Nginx errors | `/var/log/nginx/magnolia-error.log` |

CloudFront can return 502, 503, or 504 while Magnolia starts. If startup fails, inspect the installation and service logs, then check the ALB target's health in AWS. After correcting the cause, restart the services. If Magnolia has reached its restart limit, run `sudo systemctl reset-failed magnolia` before restarting it.

## CI configuration

Pull requests run formatting and validation checks. Eligible same-repository pull requests also run an AWS plan using temporary credentials. The plan check reports proposed changes and never applies them.

The existing GitHub Actions configuration uses these repository variables:

| Variable | Purpose |
| --- | --- |
| `AWS_PLAN_ROLE_ARN` | AWS role used to run the plan |
| `TF_STATE_LINEAGE` | Identifies the expected Terraform state |
| `TF_STATE_IDENTITIES_SHA256` | Checksum of the expected AWS resource IDs |

After a deployment creates, replaces, or removes resources, verify the resulting state and update `TF_STATE_IDENTITIES_SHA256` using the algorithm in [the planning workflow](../.github/workflows/terraform-plan.yml). Otherwise, the next PR plan will fail its resource-identity check. If CloudFront resources change, also check the specific resource permissions in `bootstrap/main.tf`.

A plan with proposed changes can pass CI; passing means the check succeeded, not that there are no changes. See [the architecture document](architecture.md#terraform-state-and-ci) for the access controls.

## Backend state

Terraform state records which AWS resources Terraform manages. The application infrastructure uses the existing S3 bucket `crescendo-exam-tfstate-317399646022-eu-central-1`:

| Object path in the bucket | Purpose |
| --- | --- |
| `workload/terraform.tfstate` | State used by `infra/` |
| `workload/terraform.tfstate.tflock` | Temporary lock preventing concurrent state changes |
| `bootstrap/terraform.tfstate` | Recovery copy of the local state used by `bootstrap/` |

Routine deployments use `infra/`. The separate `bootstrap/` configuration manages the state bucket and CI access. After changing those resources, back up its local state in restricted storage and at the S3 recovery path. Keep an independent copy outside the bucket before teardown.

## State recovery

State recovery is needed only if Terraform's record is lost or damaged. Stop CI and other Terraform operations first. Preserve the current state before restoring a previous S3 version, and check that the restored record matches the actual AWS resources before applying anything. Restoring Terraform state does not restore CMS content.

For `bootstrap/`, restore its local state from the recovery copy or an independent backup. Check that Terraform recognizes the existing resources and proposes no changes before resuming operations. Do not apply with missing state: Terraform may try to create resources that already exist.

If Terraform reports a stale lock, confirm that the operation holding it has stopped before using `terraform -chdir=infra force-unlock LOCK_ID`.

## Teardown

AWS charges continue while the stack is running. When you are ready to remove it:

1. Disable PR planning and stop other Terraform operations. Save both Terraform states and any needed CMS content outside the resources being removed.
2. Create and review a workload destruction plan with `terraform -chdir=infra plan -destroy -out=../build/operations/destroy.tfplan`. Apply that saved plan with `terraform -chdir=infra apply ../build/operations/destroy.tfplan`. This deletes the instance and CMS data.
3. Remove the bootstrap resources last, keeping their final state outside the bucket. Review a bootstrap destruction plan after deliberately removing the bucket's `prevent_destroy` protection. The bucket must be empty, including retained versions and delete markers, before Terraform can delete it. Remove the GitHub OIDC provider only if no other roles use it.
