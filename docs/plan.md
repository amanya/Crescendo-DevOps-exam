# Crescendo DevOps exam: plan and progress

Updated: 2026-10-15 (Europe/Madrid)

## Current position

P01 is Verified. Git is initialized on `main` with an initial local commit. Terraform 1.16.6 is installed, and the minimal configuration has initialized with AWS provider 6.69.0. Formatting, validation, ignore-rule checks, and the sensitive-content review passed.

P01 through P05 reviews passed. P05 is Verified: CloudFront is deployed, browser and authenticated HTTP checks pass through HTTPS, and the replacement private instance serves Magnolia through a healthy ALB target. Independent review confirmed the live CloudFront settings, passing anonymous checks, and a fresh no-change drift plan. Login, CSRF rejection, AdminCentral, Travel content/assets, session reuse, anonymous isolation, and logout passed without exporting credentials or cookies. Browser HTTPS terminates at CloudFront; origin connections use unencrypted HTTP for this development scope. P06 is Verified: protected S3 state is active, the original lineage and all 33 managed resource IDs are preserved, and actual PR formatting/validation/OIDC planning passed with no changes. P07's dependencies are satisfied and P07 is Ready. The P06 PR remains open at this review checkpoint. The stack remains running.

## Agreed scope

- AWS profile: `default`; workload region: `eu-central-1`.
- Account: `317399646022`; verified identity: `amanya-crescendo`.
- Use Terraform, as required by the exam. This takes precedence over the AWS Agent Toolkit's general preference for CDK or CloudFormation.
- Two public and two private subnets across two availability zones; Internet Gateway, one NAT Gateway, and route tables.
- One private EC2 instance running Java, Tomcat, Magnolia Community Edition, and Nginx.
- One EBS root volume for the OS, software, and CMS data, deleted on termination. Use the AWS account and AMI defaults for encryption.
- Keep content through reboots and stop/start cycles. Replacing the instance reinstalls the software and starts a fresh CMS.
- Request path: browser -> CloudFront -> ALB -> Nginx -> Tomcat/Magnolia.
- Run Terraform formatting checks, validation, and a real plan on trusted PRs through GitHub Actions.
- Document architecture, setup, required configuration/secrets, assumptions, limitations, and teardown in the README.
- Keep the repository private following the user's post-P06 request. Confirm the submission access/visibility requirement during P07, provide CloudFront screenshots or video, send the requested collaborator invitations, and prepare for the walkthrough. Do not restore public visibility without authorization.
- Leave a separate data volume, RDS, automatic instance replacement, and application high availability for later iterations.

## Proposed working agreement

1. Discuss the work in chat and record decisions that affect implementation in this plan. Keep progress here too.
2. The user chooses the scope and priorities and can review or redirect work at any checkpoint. The primary agent keeps the plan current and integrates changes.
3. Read `AGENTS.md`, this plan, and the relevant code at the start of each implementation session. Check existing changes before editing.
4. Name the task you're starting, update its status as it progresses, and report findings or blockers in chat.
5. Mark a task verified when there's evidence that it meets its acceptance criteria. Record commands, CI runs, or demo evidence. Keep credentials, state contents, and sensitive plan output out of the record.
6. Update decisions and dependencies when they change. Keep the task table current; a detailed activity diary isn't needed.
7. Make small changes that can be reviewed by task. Once Git is initialized, use its history to track implementation details.
8. At each checkpoint, report what changed, what was checked, any limitations, and the next task. Adjust the plan based on review feedback.
9. Use AWS MCP and the relevant retrieved skills as described in `AGENTS.md`. Define the infrastructure in Terraform.

## Task board

Tasks move through Ready, In progress, and Verified. Queued tasks are waiting for dependencies; Blocked tasks need an issue resolved. Unassigned tasks haven't been started or delegated.

| ID | Task | Status | Dependencies | Owner |
| --- | --- | --- | --- | --- |
| P00 | AWS access | Verified | None | Primary agent |
| P01 | Repository and tooling | Verified | P00 | Primary agent |
| P02 | Magnolia provisioning | Verified | P00 | Primary agent |
| P03 | VPC, EC2, and ALB | Verified | P01, P02 interface | Primary agent |
| P04 | Application integration | Verified | P02, P03 | Primary agent |
| P05 | CloudFront | Verified | P04 | Primary agent |
| P06 | Remote state and PR checks | Verified | P01, P03 | Primary agent |
| P07 | Lifecycle and submission | Ready | P04, P05, P06 | Unassigned |

### P00: AWS access

- AWS MCP `STS.GetCallerIdentity` succeeded for account `317399646022` and user `amanya-crescendo`, with `eu-central-1` selected.
- Authentication works. We still need to check permissions for the deployment operations.

### P01: Repository and tooling

- Initialize Git and ignore Terraform state, local configuration, generated artifacts, and secrets.
- Install Terraform, record Terraform/provider version constraints, and commit the provider dependency lock file.
- Create directories as their files are needed and start the README.

Done when Git is initialized, ignore rules protect local configuration/state/artifacts/secrets while retaining the provider lock file, Terraform is installed, minimal Terraform/provider configuration uses profile `default` and region `eu-central-1`, local initialization generates the lock file, and the README explains purpose, prerequisites, setup, and deployment status. Formatting, validation, and a sensitive-content review must pass before the initial local commit. Remote state, resource creation, CI, and publication remain in later tasks.

Verified on 2026-10-15; validation evidence is recorded below. P03's P01 dependency is satisfied. The P02/P03 application interface is agreed, and P03 verification also makes P06 Ready.

### P02: Application provisioning

- Choose a Community Edition artifact we can download, pin its version, and check which Java/Tomcat versions work with it.
- Work out first-run initialization, application paths, and embedded persistence settings.
- Write readable bootstrap, Nginx, and systemd configuration. Make installation and startup failures visible in the logs.
- Before infrastructure work proceeds in parallel, agree on the Nginx target port, Magnolia context path, readiness check, and Terraform template inputs.

Done when we've checked artifact access and version compatibility and have an installation procedure ready to deploy. P04 checks that it runs on EC2.

Verified on 2026-10-15 for those preparation criteria; evidence is recorded below. P03 now consumes the interface below without changing the templates. Runtime acceptance remains with P04.

### P02/P03 interface

P02 owns `infra/templates/bootstrap.sh.tftpl`, `infra/templates/nginx.conf.tftpl`, `infra/templates/magnolia.service.tftpl`, and the local checker `scripts/check-provisioning.py`. The primary agent maintains README and plan changes. No other agent was dispatched. P03 can use this interface without changing the application templates:

| Item | Contract |
| --- | --- |
| Magnolia | CE Travel Demo 6.3.27, official public Nexus ZIP linked from [Magnolia's 6.3 releases](https://docs.magnolia-cms.com/product-docs/6.3/releases/); exact URL and SHA-256 are in README and bootstrap |
| Artifact pin | SHA-256 `8ba8ea6bcaffb7c6f6895d2ed024e322bfed546f6e475c710018b7a3b16b1a99`; top directory `travel-demo-community-webapp-6.3.27/apache-tomcat-9.0.121` |
| Runtime | Bundled Tomcat 9.0.121; Ubuntu `openjdk-17-jre-headless`, Java home `/usr/lib/jvm/java-17-openjdk-amd64`; keep repository patch updates |
| OS and CPU | Ubuntu Server 24.04 LTS with cloud-init/systemd, x86_64 (`amd64`). Bootstrap rejects another release or architecture. P03 selects the AMI |
| Sizing | Heap `-Xms256m -Xmx2048m`; allow at least 4 GiB RAM. P03 selects `t3.medium` (2 vCPUs, 4 GiB RAM), standard CPU credits, and a 30 GiB gp3 root disk; P04 checks memory/disk use and CPU-credit/startup behavior |
| Terraform rendering | `nginx.conf.tftpl` and `magnolia.service.tftpl` each take `{}`. Base64-encode each rendered result and pass strings `nginx_config_b64` and `magnolia_service_b64` to `bootstrap.sh.tftpl`; assign rendered bootstrap to `user_data`. README includes the complete expression. No credential inputs |
| Fixed configuration | Package URL/checksum, ports, paths, and context are pinned in the templates. Keep them together when reviewing an update. User-data changes should replace the instance so the package and CMS are rebuilt |
| Nginx target | HTTP `80`, default host; only ALB security-group ingress. `/` redirects to `/magnoliaAuthor/`. Other webapps are removed |
| Tomcat | HTTP `127.0.0.1:8080`; shutdown socket disabled; no AJP connector. Do not expose port 8080. Local Nginx is the trusted forwarded-header proxy |
| Magnolia context | `/magnoliaAuthor`, author only, with the CE Travel Demo. No second public webapp or publishing target |
| Readiness | ALB GET `/magnoliaAuthor/.rest/health/ready` through Nginx on port 80; matcher `200` only, no redirect success codes. Suggested interval 30 seconds, timeout 5 seconds, healthy threshold 2, unhealthy threshold 3. Confirm timings in P04 |
| Initialization | `magnolia.update.auto=true`; generate a local random initial administrator password directly into a restricted file and use Magnolia's file-based bootstrap setting; disable interactive fallback; leave the admin readiness probe enabled |
| CMS configuration | Keep `magnolia.home` at the webapp root to retain bundled modules and author MicroProfile configuration. Preserve bundled `jackrabbit-bundle-h2-search.xml` with embedded H2 and file datastore |
| Data paths | `/var/lib/magnolia/repositories` holds databases, datastore, and indexes; sibling `tmp`, `cache`, `history`, and `keys` directories hold other mutable files. `/etc/magnolia/superuser-password` is `root:magnolia`, `0640`; `/etc/magnolia` is `0750` |
| Installation and logs | Tomcat/webapp `/opt/magnolia`; Magnolia logs `/var/log/magnolia`; Tomcat logs/work/temp inside `/opt/magnolia`; bootstrap `/var/log/magnolia-bootstrap.log` and cloud-init output; process output in the Magnolia journal; Nginx logs `/var/log/nginx/magnolia-{access,error}.log` |
| Service order | Configure packages/files, run native Nginx and unit checks, enable services, start Magnolia, wait for exact 200 readiness, then start Nginx. The Nginx systemd drop-in uses `Wants`/`After=magnolia.service` for subsequent boots. It may serve an unhealthy response if Magnolia fails |
| Startup failure | ERR trap logs line and exit status; JVM runs in foreground under systemd. Readiness tries 120 times with 5-second pauses and up to 5-second requests; unit startup timeout 1500 seconds. Restart on failure after 15 seconds, capped at 3 starts per 1800 seconds |
| Persistence | One root volume, no extra mounts. Reboots reuse directories. Bootstrap reruns preserve a matching installation and data; a new instance starts fresh. P03 must set root-volume delete-on-termination and omit explicit encryption/key overrides |
| Network prerequisites | Outbound DNS plus HTTP/HTTPS access to Ubuntu package repositories and HTTPS to `nexus.magnolia-cms.com`, available before cloud-init installs packages. P03 owns routing/NAT and Systems Manager access |

The selected package uses Magnolia 6.3 requirements despite the exam's 6.2 documentation link. [Magnolia's 6.3 stack](https://docs.magnolia-cms.com/performance-tuning/6.3/system-requirements/certified-stack/) and [Apache's version table](https://tomcat.apache.org/whichversion.html) support Java 17 with Tomcat 9. [Magnolia configuration](https://docs.magnolia-cms.com/product-docs/6.3/administration/architecture/configuration-management/), [administrator setup](https://docs.magnolia-cms.com/product-docs/6.3/administration/security/set-superuser-password/), and [readiness API](https://docs.magnolia-cms.com/product-docs/6.3/developing/api/health-check-api/) explain the first-run and health behavior. The downloaded core and REST source archives also confirm automatic module installation and readiness registration for module initialization, datastore availability, and administrator setup.

P04 verified apt installation and the native systemd unit, first-run modules and administrator setup without browser intervention, initialized sample content and private login, readiness returning 200 only after initialization, unhealthy responses while Magnolia is stopped, service recovery, ALB registration, and HTTP redirects/assets/sessions. Reboot reused the data paths and credentials. P07 records the full content-retention and instance-replacement demonstration. Keep credential values and unsanitized application logs out of evidence. Browser HTTPS and the forwarded protocol through CloudFront remain P05 checks.

At the P02 checkpoint, EC2 execution was unverified; P04 now supplies the runtime evidence. Remaining provisioning limits: Java/Nginx patch versions follow apt repositories; the ZIP checksum is locally calculated from an official HTTPS download without a separate vendor signature; embedded H2, one author webapp, one disk, and no content backup remain deliberate exam limits. The local installation checker does not prove application readiness, reboot persistence, or successful recovery.

### P03: Infrastructure

- Build the required VPC layout and routing, one NAT Gateway, security groups, private EC2 instance, ALB, and target group.
- Delete the root disk on termination and use the default encryption behavior.
- Configure Systems Manager access and pass the bootstrap script through user data.
- Add useful outputs and explain the availability limits of using one instance and one NAT Gateway.

Done when formatting and validation pass, the Terraform plan matches the agreed architecture, and the code is ready to deploy.

Verified on 2026-10-15 for these preparation criteria. The real plan contains 31 additions, no changes, and no deletions. No apply was run. Files: `infra/network.tf`, `infra/compute.tf`, `infra/load-balancer.tf`, `infra/variables.tf`, `infra/outputs.tf`, and the provider update; README documents sizing, prerequisites, and limitations. P02 templates/checker remain unchanged, and its independent review update is preserved.

The VPC is `10.42.0.0/16`; public subnets are `10.42.0.0/24` and `10.42.1.0/24`, private subnets are `10.42.10.0/24` and `10.42.11.0/24`, in `eu-central-1a` and `eu-central-1b`. One shared public route table targets the Internet Gateway; one shared private route table targets the NAT Gateway and Elastic IP in public subnet `a`. EC2 uses private subnet `a` with no public IP. Explicit dependencies wait for the outbound routes, associations, instance rules, and SSM policy attachment before instance creation.

The official Canonical AMI is pinned by exact release name through `ubuntu_ami_name`, with owner/architecture/HVM/EBS/state filters. The reviewed default is `ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20261004`, resolving to `ami-0e27250725fa51794`. Pinning avoids automatic image updates replacing the instance and deleting CMS content. `t3.medium` provides 2 vCPUs and 4 GiB RAM for the 2 GiB heap plus OS/JVM overhead. Standard CPU credits avoid surplus-credit charges but may slow sustained work and first-run initialization. The single 30 GiB gp3 root disk allows space for the OS, installation staging, CMS data, and logs. It is deleted on termination and has no encryption or key override.

Systems Manager uses the AMI's preinstalled agent, a new EC2 role/profile with `AmazonSSMManagedInstanceCore`, and HTTPS through NAT. IMDSv2 is required. The instance accepts only ALB-sourced TCP 80 and sends TCP 80/443 outbound; Tomcat remains on loopback. The public ALB spans both zones, accepts HTTP 80, and sends HTTP 80 only to the instance group. Its health check uses the interface's exact path, `200` matcher, and 30/5-second interval/timeout with thresholds 2/3. Outputs cover the network, instance, AMI, NAT IP, target group, ALB hostname/zone, and author/readiness URLs.

Limits remain one instance, one root disk, and one NAT Gateway, without automatic failover or backups. Two ALB zones do not provide application high availability. Both private subnets depend on NAT in zone `a`; future zone `b` egress crosses zones. HTTP is unencrypted and the ALB is publicly reachable; P05 owns browser HTTPS and the origin policy. P04 subsequently verified deployment access, available quotas/capacity, the running SSM Agent, and bootstrap/application behavior. P05 and P06 are Ready after the P04 checkpoint.

### P04: Application integration

- Apply the infrastructure and inspect bootstrap and service logs.
- Check installation, service startup, and target registration. ALB health checks must reflect whether Magnolia is available.
- Check that Magnolia is ready to serve requests. Terraform apply completing doesn't confirm application readiness.

Done when a fresh instance installs and configures Magnolia automatically, completes first-run setup, and serves it through the ALB.

Verified on 2026-10-15. The fresh instance provisioned from the committed P02/P03 Terraform and templates without manual application setup or bootstrap fixes. Readiness returned exact 200 only after initialization; the ALB served Magnolia's login page and assets. Private authenticated checks confirmed 95 modules, Travel content, session rotation/reuse, and logout. Stopping Magnolia caused failed readiness and an unhealthy ALB target; restart and reboot restored health. Reboot reused the repository, sample node identifier, and password file, and private login passed again. Sizing, CPU credits, native configuration, SSM/NAT, and live ingress restrictions were checked. The final drift plan has no changes. Sanitized evidence is below and deployed IDs/endpoints are in README.

P05 is Ready and must verify browser HTTPS, the origin policy, forwarded protocol, and authenticated browser sessions through CloudFront. P06 remains Ready and must migrate the existing local state. P07 still waits for P05/P06 and owns newly created content retention and the replacement demonstration. No P04 blocker remains. The review checkpoint leaves the 31-resource stack running and billable; no CloudFront, remote backend, CI, or publication was added.

### P05: CloudFront

Verified on 2026-10-15. The existing ALB is the origin, using the default CloudFront hostname/certificate, viewer HTTP-to-HTTPS redirects, disabled caching, and complete application request forwarding. HTTP-only origin traffic is a documented development limit. Provisioning changes replaced the instance and intentionally reset its CMS root disk. Browser/HTTP login, CSRF protection, redirects, assets, AdminCentral, sample content, session-cookie attributes/reuse, anonymous isolation, logout, native checks, health, and drift all passed. The P04 independent-review update and local state are preserved. P06 is the next task; P07 now waits only for P06.

- Configure the ALB origin, browser HTTPS, and an explicit origin connection policy.
- Start with caching disabled and forward what the application needs for its sessions and requests.
- Check pages, static assets, redirects, and login/session behavior through CloudFront.

Done when Magnolia works in a browser through the CloudFront URL and we've documented the origin encryption choice and its limitations.

### P06: State and CI

- Set up protected remote Terraform state. Document how to bootstrap it, migrate state, and clean it up.
- Configure repository-scoped AWS OIDC access for trusted PR planning.
- Publish the reviewed source repository as needed to run the actual PR checks. Collaborator invitations and final submission preparation remain P07 work.
- Run `terraform fmt -check`, `terraform validate`, and `terraform plan` on PRs.
- Decide how to handle untrusted/fork PRs without giving them AWS access. Keep deployment manual for the first version.

Done when an actual PR passes the checks and produces a real plan against the intended state.

P06 must preserve and migrate the existing local state, verify the same resource identities after migration, and confirm the workload plan still has no changes. The provider's hardcoded profile was removed so local default-profile use and GitHub's OIDC environment credentials both work. The real PR requires publishing the source repository during P06. Use native S3 state locking to keep the backend small, and restrict the CI role to the reads needed for planning plus access to the state and its lock object.

P06 Verified on 2026-10-15. The separate Terraform bootstrap, restricted backups/recovery copy, migration, local no-change plans, health checks, and [actual PR checks](https://github.com/amanya/Crescendo-DevOps-exam/actions/runs/38732314501) pass. The original lineage and all 33 managed IDs are preserved; CI reports plan exit 0 and 33 no-op actions. The previously uncommitted P05 independent review update is preserved in commit `4c7543f`. The repository is `amanya/Crescendo-DevOps-exam` (made private at the user's request after P06 verification); [PR #1](https://github.com/amanya/Crescendo-DevOps-exam/pull/1) stays open for review. No workload apply or instance replacement occurred. P07 is Ready; stop at the P06 review point.

### P07: Verification and submission

- Create content, reboot the instance, and check that the content survives.
- Replace only the instance through Terraform. Check that provisioning runs automatically and a fresh CMS loads through the same CloudFront distribution.
- Finish the README: architecture, prerequisites, commands, configuration, troubleshooting, limitations, and teardown.
- Capture CloudFront screenshots/video and prepare walkthrough notes.
- Confirm the private `Crescendo-DevOps-exam` repository's submission access/visibility requirement and invite `tristanamargo-crescendo` and `jeremysummers`. Do not restore public visibility without authorization.

Done when we have evidence for the lifecycle checks, the documentation matches the deployment, CI passes, and the submission requirements are met.

## Proposed repository layout

Create directories when their first files are needed:

```text
AGENTS.md                       Agent instructions
README.md                       Setup, architecture, and operations
docs/
  plan.md                       This plan, decisions, and progress
  evidence/                     Screenshots or other sanitized demo evidence
infra/
  versions.tf                   Terraform/provider constraints
  providers.tf                  Provider configuration
  variables.tf                  Inputs
  network.tf                    VPC, subnets, routing, NAT
  compute.tf                    EC2, IAM instance role, security groups
  load-balancer.tf              ALB and target group
  cloudfront.tf                 CloudFront configuration
  outputs.tf                    Deployment outputs
  templates/                    Bootstrap, Nginx, and service templates
scripts/                        Local operational helpers, if needed
.github/
  workflows/                    PR checks
```

Give remote-state bootstrap configuration a small directory of its own if needed. Keep Terraform simple for this single-environment exercise; a reusable module framework isn't needed.

## Review checkpoints

1. After foundation and application planning, review the installation choices, file layout, and initial Terraform plan.
2. Once Magnolia runs through CloudFront, review the deployment and the decisions behind it.
3. Review a successful CI run on a PR and the reboot/replacement evidence.
4. Before submission, review the final README, diagram, limitations, and demo evidence.

## Using multiple agents later

When the user asks for multiple agents, divide the work by task and file:

- Application agent: P02, owning the application templates.
- Infrastructure agent: P03, owning networking, compute, and ALB Terraform files.
- CI agent: P06, owning the workflow and state-bootstrap files once we've agreed on state and identity conventions.
- Primary agent: shared interfaces, integration, verification, this plan, and final README consistency.

Before assigning work, record each agent's files, dependencies, acceptance criteria, and interface decisions. Give each file one editor at a time. Agents report their changed files, validation results, and unresolved issues to the primary agent, who integrates the changes and checks that the parts work together before marking tasks verified.

P02 and P03 can run in parallel once their shared interface is agreed. P04 needs both to finish. Use additional agents where the tasks can proceed independently enough to make the coordination worthwhile.

## Decisions

Agreed on 2026-10-15:

- The exam requires Terraform.
- The user chose profile `default` and region `eu-central-1`.
- Start with embedded Magnolia persistence to keep the first deployment small.
- Keep all data on the EBS root disk and delete it on termination. The user accepts fresh CMS data when the instance is replaced.
- Start with the simplest working EC2 deployment. Consider separate persistent storage and automatic replacement in later iterations.
- Let editors wrap documentation prose; do not enforce a fixed line length.
- Use the AWS account and AMI defaults for EBS encryption. The user wants the standard setup without an explicit encryption override or custom keys.
- P01 uses Terraform `~> 1.16.6` and AWS provider `~> 6.69.0`, allowing patch updates within each minor release. HashiCorp's official [Terraform release metadata](https://releases.hashicorp.com/terraform/index.json) and [AWS provider registry metadata](https://registry.terraform.io/v1/providers/hashicorp/aws) confirmed these stable versions. Keep the generated provider lock file tracked. Use the default local backend until P06.

## Evidence and blockers

- P00: AWS MCP `run_script` returned a successful `STS.GetCallerIdentity` API call for the expected account and IAM user.
- AWS MCP `EC2.GetEbsEncryptionByDefault` returned `false` for `eu-central-1` on 2026-10-15. The account setting will be left unchanged.
- P01 tooling check: Git 2.50.1, AWS CLI 2.35.13, GitHub CLI 2.95.0, and Homebrew 7.0.1 ran on macOS arm64. Terraform was missing and was installed as version 1.16.6 through HashiCorp's official Homebrew tap.
- P01: `terraform -chdir=infra init -input=false` succeeded using the local backend and installed AWS provider 6.69.0, signed by HashiCorp. The generated `infra/.terraform.lock.hcl` records its version and checksums.
- P01: `terraform -chdir=infra fmt -check -recursive` passed. `terraform -chdir=infra validate -no-color` reported a valid configuration. The sandbox prevented the provider schema process from starting on the first attempt; validation passed with the required local process permissions.
- P01: `git check-ignore` checks passed for 51 excluded paths and 8 retained paths, including `infra/.terraform.lock.hcl`. The rules cover local state, variable files, plans, credentials, environment files, and generated artifacts. Only `infra/` was added to the existing directory layout, with useful configuration files.
- P01: all seven staged files were reviewed. A sensitive-content pattern scan found no AWS access keys, private keys, GitHub tokens, literal credential assignments, or credentials embedded in URLs. `git diff --cached --check` passed, and local README/plan links resolve. The existing `AGENTS.md` was preserved unchanged and included in the initial local commit.
- P01: the initial local commit was created on `main` with the instructions, plan, README, ignore rules, Terraform configuration, and provider lock file. No AWS resources have been defined or created, and no plan/apply, remote-state setup, CI, or publication was performed.
- P01 review: checked commit `ca4ffb7` with a clean working tree. Formatting, Terraform validation, representative ignore rules, local documentation links, and whitespace checks passed. Validation required permission for the local provider process to run outside the sandbox. No issues blocking P02 were found.
- P02 artifact check on 2026-10-15: anonymous HTTPS GET of the official CE Travel Demo 6.3.27 bundle returned HTTP 200 and 251,521,274 bytes. ZIP CRC/integrity passed. Inspected `magnolia-core-6.3.27.jar`, Tomcat `ServerInfo.properties` (`9.0.121`), H2 `2.4.240`, Jackrabbit `2.22.8-magnolia`, and the H2 repository XML. Bootstrap pins the downloaded SHA-256. No archive is tracked.
- P02 compatibility: fetched official Magnolia 6.3 stack, configuration, and readiness documentation, plus Apache's Tomcat compatibility table and Ubuntu's OpenJDK 17 package/file list. The actual artifact matches Java 17/Tomcat 9 requirements. Administrator setup documentation and exact-version core sources confirm file-based unattended setup is also required in this release.
- P02 local checks: Terraform's real `templatefile` renderer succeeded for all three templates in an isolated directory, without provider initialization or AWS access. `bash -n` passed for bootstrap, generated `setenv.sh`, and generated readiness helper; embedded Python compiled. The actual archive's properties/XML accepted the provisioning transform twice without further changes, including the loopback connector and disabled shutdown port. Rendered user data is 9,442 bytes, below EC2's 16 KiB raw limit. `scripts/check-provisioning.py --archive <local-zip>` repeats these checks. Core class-file major version 61 confirms Java 17 bytecode. Mocked readiness checks accepted 200 and rejected 302, 503, and connection-failure status; these are local helper checks, not application runtime evidence.
- P02 configuration checks: ShellCheck 0.11.0 passed the rendered bootstrap and readiness helper with only SC1091 excluded for the target OS's `/etc/os-release`. Nginx 1.24.0 compiled from official source passed `nginx -t` against the rendered site in an HTTP wrapper, relocating log paths into `/tmp` on macOS. No server was started. Docker was unavailable, so native Ubuntu/systemd checks remain P04 work; bootstrap includes `nginx -t` and `systemd-analyze verify` before startup.
- P02 review: all six changed files were inspected, the P01 review update was preserved, local README/plan links resolve, Terraform formatting and whitespace checks passed, and a sensitive-content pattern scan found no AWS access keys, private keys, GitHub tokens, literal credential values, or credentials in URLs. Generated downloads and rendered files stay outside Git. Unit sections and commands were inspected; native systemd verification remains pending.
- P02 independent review: checked commit `f6d23c3` with a clean working tree. Re-ran the provisioning checker against the downloaded archive: checksum, ZIP integrity, bundled versions, embedded persistence, repeatable transforms, template rendering, Bash syntax, and embedded Python compilation passed. Rendered user data is 9,442 bytes. ShellCheck 0.11.0 and the local Nginx configuration check passed; Nginx required permission to run its macOS sysctl check outside the sandbox. The checked Nginx site matches the rendered template with only log paths relocated. Formatting, whitespace, and local documentation file-link checks passed. No blocking findings for P02's preparation scope; native Ubuntu/systemd and Magnolia runtime checks remain P04 work.
- P03 AWS lookup: AWS MCP retrieved compute, networking, IAM, and instance-profile guidance and checked official VPC/SSM/ALB documentation. Successful `STS.GetCallerIdentity`, `EC2.DescribeImages`, `EC2.DescribeInstanceTypes`, `EC2.DescribeAvailabilityZones`, and `EC2.DescribeInstanceTypeOfferings` calls confirmed the expected account, Canonical owner, Ubuntu 24.04 x86_64 release, 4 GiB/2-vCPU `t3.medium`, and its offering in both chosen zones. Availability is not a reservation or a deployment-permission check.
- P03 checks: `terraform -chdir=infra fmt -check -recursive`, `terraform -chdir=infra validate -no-color`, and `git diff --check` passed. Validation required the local provider process to run outside the sandbox. `python3 scripts/check-provisioning.py` passed; repeating with `--archive /private/tmp/crescendo-p02/magnolia.zip` and ShellCheck 0.11.0 on PATH passed Bash syntax, embedded Python compilation, archive checksum/integrity, versions, persistence, and repeated transforms.
- P03 real plan: `terraform -chdir=infra plan -input=false -no-color -out=../build/p03/p03.tfplan` succeeded against AWS with profile `default` in `eu-central-1`, using Terraform 1.16.6 and AWS provider 6.69.0. It proposes 31 creations, no changes, and no deletions. The saved plan, JSON/text output, and dependency graph remain under ignored `build/p03/`. No apply or AWS mutation was performed.
- P03 plan review: inspected the plan, its JSON configuration/references, and `terraform graph -type=plan`. Local assertions passed for resource counts, provider/account, distinct two-zone subnets, IGW/NAT routes and all four associations, private placement/no public IP, instance profile/SSM attachment, ALB-only ingress, restricted egress, one 30 GiB gp3 root with deletion and omitted encryption/key overrides, listener/target attachment, and exact readiness timings/matcher. Graph traversal confirmed EC2 waits for NAT, IGW, routes, associations, egress rules, and the SSM policy. Rendered user data equals the P02 checker output byte for byte (9,442 bytes); decoded embedded Nginx and service files also match.
- P03 final review: reviewed all eight changed files, preserved the existing P02 independent review, and left the P02 templates/checker, provider lock, and agent instructions unchanged. Local documentation file links, sensitive-content pattern checks, and representative ignore checks for generated plans/state/artifacts passed. The provider lock remains tracked. The changes are ready for a focused local P03 commit.
- P03 independent review: checked commit `c8b516a` from a clean working tree. Formatting, validation, provisioning rendering/syntax checks, and whitespace checks passed. A fresh read-only plan saved to ignored `build/p03/review.tfplan` again proposes 31 creations, no changes, and no deletions. Its configuration and planned values match the original P03 plan. Reviewed the source and rechecked the saved plan and fresh dependency graph for account/region, subnets/routing, private EC2 placement, IAM/SSM, security groups, root lifecycle/default encryption, readiness settings, and prerequisite dependencies. Rendered user data matches P02 byte for byte at 9,442 bytes; the P02 templates/checker are unchanged. No blocking findings for the preparation scope. No apply was run.
- P03 had no preparation blocker and its independent review passed. Its P04 handoff required a fresh reviewed plan, deployment permissions/quotas, an authorized apply, and checks for SSM Online, NAT downloads, native configuration checks, bootstrap/initialization, ALB health and failure/recovery, loopback/SG restrictions, private login, assets/redirects/sessions, sizing/credits, and reboot reuse. P07 owns the full lifecycle demonstration. CloudFront, remote state, CI, and publication remain later work.

- P04 scope and skills: deployment and runtime checks were authorized for account `317399646022`, profile `default`, region `eu-central-1`, on 2026-10-15. Preserved the existing uncommitted P03 independent review. Retrieved AWS compute and Systems Manager guidance with AWS MCP; used the humanizer skill for prose. Loaded the cached `aws-secrets-manager` skill and checked it against the official Toolkit source. Because `asm-exec` references do not cover the planned local password file, the user explicitly authorized the private SSM/loopback exception. No password, session cookie, or credential-derived hash entered evidence, logs, or public HTTP.
- P04 preflight: AWS MCP confirmed account, AMI availability, and both zones. Before creation, quotas had room: 64 standard on-demand vCPUs (none running), five VPCs (one used), five EIPs (none used), five NAT Gateways per zone (none used), and 50 ALBs (none used). IAM simulation allowed key deployment, pass-role, service-linked-role, and SSM Run Command actions; the successful apply confirmed actual deployment access. Formatting, Terraform validation, and the provisioning checker with the pinned archive and ShellCheck 0.11.0 passed. The fresh ignored `build/p04/deploy.tfplan` had 31 creations and no changes/deletions; reviewed architecture, dependencies, security groups, root disk, credits, metadata, readiness, and byte-identical 9,442-byte bootstrap before apply.
- P04 deployment: Terraform applied that plan with 31 added, no changes or deletions. Local state and backup remain in ignored `infra/terraform.tfstate` and `infra/terraform.tfstate.backup`; plans, outputs, and apply logs remain under ignored `build/p04/`. Instance `i-07fcc5e12ec293cdb` has private IP `10.42.10.96` and no public IP. SSM agent `3.3.4793.0` is Online. NAT `nat-083d0e0c9070b58d4` is available; the instance's HTTPS egress check returned its exact EIP `18.195.185.6`. The ALB is `crescendo-exam-1001328653.eu-central-1.elb.amazonaws.com`; README records its endpoints and resource IDs.
- P04 provisioning: cloud-init reached `done`, exit 0, with one bootstrap completion marker and no bootstrap failure. Native `nginx -t` and `systemd-analyze verify` exited 0. Installed OpenJDK `17.0.20.1`, Nginx `1.24.0-2ubuntu7.18`, and the pinned Magnolia/Tomcat bundle. Readiness was unavailable during initialization, then returned exact HTTP 200 through Tomcat, Nginx, and ALB with `magnolia-instance`, `datastore`, and `admin-setup` all UP. Both services became active about nine minutes after launch; Tomcat reported 407,435 ms. Magnolia logged one invalid-key-length fallback; exact-version `SecurityUtil` source confirms fallback to its default, and all initialization/login checks passed. No out-of-memory markers or unexpected service restarts were observed.
- P04 sizing: the first healthy snapshot showed about 953 MiB JVM cgroup memory (1,775 MiB peak), 2,409 MiB available RAM, 2.80 GiB disk used, 25.20 GiB free, and a 50 MiB repository. AWS confirmed standard CPU credits. CloudWatch showed zero initial credits and roughly 20% CPU during initialization; idle periods earned about one credit, later startup consumed credits, and surplus balance/charges stayed zero. The settled post-reboot snapshot showed about 1.16 GiB JVM cgroup memory (1.78 GiB peak), 2.33 GiB available RAM, 2.81 GiB disk used, 25.20 GiB free, and a 48 MiB repository. These are startup/demo observations, not a capacity or endurance test.
- P04 behavior: `/` and `/magnoliaAuthor` redirect to the ALB author URL. Unauthenticated author/content requests return Magnolia's HTTP 401 login page; the browser rendered it and four public login assets returned 200. Private login through SSM and loopback Nginx returned 302, rotated the session, and allowed AdminCentral, the initialized Travel page/REST node, and six referenced content assets at 200. There were 95 installed module nodes. Subsequent requests reused the session; logout returned 302 and access returned to 401. The cookie was HttpOnly, scoped to `/magnoliaAuthor`, and not Secure over local HTTP. Authenticated browser behavior through CloudFront remains P05 work.
- P04 failure/recovery: a guarded Magnolia stop completed in 1.81 seconds. Tomcat readiness failed to connect; Nginx and public ALB readiness returned 502. AWS MCP observed `unhealthy`, `Target.ResponseCodeMismatch`, with 502. Systemd restart reached readiness in 57.64 seconds (Tomcat 54,931 ms); public readiness returned 200 and the target became healthy. The four-minute fallback timer was cleared after recovery and did not remain after reboot. A sole unhealthy ALB target can still receive requests, so the returned 502 and target state were both checked.
- P04 reboot: AWS MCP `EC2.RebootInstances` succeeded. The boot ID changed; SSM returned Online, both services recovered automatically with zero unexpected restarts, and cloud-init reached `done` without rerunning bootstrap. Tomcat reported 109,415 ms. Private login, sample page/assets, 95 modules, session behavior, and logout passed again. A local comparison confirmed the same sample node identifier, repository directory inode, and password-file inode; the temporary comparison marker was removed. Tomcat remained bound only to loopback 8080, with no shutdown/AJP listener. Live security groups allow instance ingress only on TCP 80 from the ALB, and the attached 30 GiB gp3 root remains deleted on termination and unencrypted under the account/AMI defaults.
- P04 final checks: AWS MCP observed the target healthy and SSM Online after reboot; public readiness returned exact HTTP 200. `build/p04/final.tfplan` reports no changes against the running stack. No Terraform or provisioning-template changes were needed, so the successful fresh-instance test uses the already committed configuration. Two helpers retain sanitized runtime and private login checks. README and this plan record the actual system, limitations, and P05/P06 readiness. Local state and generated artifacts remain outside Git. Final source/documentation review and commit complete this checkpoint.

- P04 source review: inspected both helpers and all README/plan changes. The final helpers ran successfully through AWS MCP/SSM; source compilation, local documentation links, formatting, archive/provisioning checks with ShellCheck, whitespace checks, sensitive-content patterns, and ignore checks passed. The P03 independent-review text is preserved. Only README, this plan, and the two runtime helpers are included in the P04 commit; Terraform, templates, the provider lock, and AGENTS.md are unchanged. No unresolved P04 issue remains.
- P04 independent review: checked commit `8c4cab1` from a clean working tree, reviewed both diagnostic helpers and runtime evidence, and confirmed Terraform/templates are unchanged from P03. Python compilation, formatting, whitespace, local documentation file links, and ignore checks passed. Live read-only AWS MCP checks found the expected private instance running without a public IP, EC2/system/EBS status checks OK, SSM Online, and the target healthy. Unauthenticated ALB checks returned a root redirect, the expected 401 login form, and exact HTTP 200 readiness with all three checks UP. A fresh read-only drift plan in ignored `build/p04/review-plan.txt` exited 0 with no changes. No blocking findings for P04. Credential, stop/start, and reboot tests were reviewed from the recorded P04 evidence rather than repeated. P05 must check HTTPS forwarding for both Nginx redirects and Tomcat, public hostname preservation, Secure cookies, caching, and authenticated behavior through CloudFront.

- P05 implementation: retrieved the CloudFront creation/caching and origin-protection guidance through AWS MCP and loaded the humanizer skill. The existing public ALB remains the origin. Browser HTTP redirects to HTTPS using the default CloudFront hostname/certificate; origin policy is explicitly HTTP-only to avoid adding a domain/certificate to this development scope. ALB ingress now uses the AWS-managed CloudFront origin-facing prefix list; it is not distribution-specific authentication. CloudFront logging, WAF, origin TLS, and private VPC origins remain outside this implementation.
- P05 predeployment review: preserved the P04 independent-review update and local state. Terraform formatting/validation, rendered Bash/Python syntax, ShellCheck 0.11.0, archive checksum/ZIP/version checks, repeatable archive transforms, and locally compiled Nginx 1.24.0 configuration validation passed. Rendered user data is 9,858 bytes. The reviewed saved plan contains five additions and three deletions: the distribution and origin request policy, an intentional EC2/root-disk replacement for Nginx user-data changes, replacement target attachment, and replacement ALB ingress rule. AMI, size, subnet, disk deletion, and encryption defaults are unchanged. A restricted ignored state copy was saved before applying the exact reviewed plan.
- P05 deployment: Terraform applied the reviewed plan successfully (five additions, three deletions). CloudFront distribution `E178D8X4DHIIP9` reached `Deployed` with hostname `d2xpkbus8fu2t7.cloudfront.net`. The replacement instance is `i-03e2b17589905593d` (`10.42.10.237`) with root `vol-0507e0dd3d123a7d3`, still unencrypted under defaults and deleted on termination. SSM is Online; Magnolia completed initialization automatically. An early browser HTTPS request returned 502 while the origin was starting; later checks confirmed readiness and recovery. Authenticated CloudFront checks subsequently passed under the user-approved P05 extension recorded below.
- P05 anonymous verification: the final checker passed viewer HTTP-to-HTTPS, relative root/context redirects, exact 200 readiness, repeated uncached 404s, the expected 401 CSRF-protected login page, three login assets, and Secure/HttpOnly/context-path CSRF cookies. Supplying spoofed HTTP forwarding headers did not downgrade the cookie. The browser rendered Magnolia's styled login form at the HTTPS CloudFront URL and recovered from the earlier startup 502 without changing the URL. Native Ubuntu Nginx and systemd checks passed, bootstrap completed, and AWS MCP found only the new target, healthy. Direct public ALB HTTP access was blocked. The post-deployment drift plan exited 0 with no changes. Authenticated acceptance subsequently passed as recorded below.
- P05 runtime/source review: cloud-init reached done with one bootstrap completion marker; both services are active with zero unexpected restarts, all three health checks are UP, and Tomcat remains on loopback. Tomcat startup was 229,362 ms, JVM cgroup memory about 962 MiB (1,860 MiB peak), available memory about 2,368 MiB, and root free space 25.19 GiB. The browser login DOM has no HTTP asset URLs or ALB asset URLs. Final formatting, whitespace, Python compilation, documentation links, sensitive-content patterns, and ignored state/artifact checks passed. Local implementation commit `9e9ea00` records the infrastructure, proxy template, checker, and documentation. P05 authenticated acceptance subsequently passed; P07 now waits for P06.
- P05 credential scope: the user explicitly approved extending the P04 local-file exception to an on-instance checker and headless browser. Credentials and session cookies may be sent only to this stack's verified CloudFront HTTPS hostname, remain in memory on EC2, and must never enter tool output, logs, chat, or evidence. Only sanitized results/screenshots leave the instance. This does not authorize exporting credentials to a workstation or using another destination. Authenticated checks passed within this scope; no credential, cookie, CSRF token value, or unsanitized response body entered output or evidence.
- P05 authenticated HTTP acceptance: the on-instance checker passed an invalid-CSRF login rejection, valid login (302), creation of a new session, Secure/HttpOnly/path `/magnoliaAuthor` session-cookie attributes, AdminCentral, Travel page/node, six sample assets, module-query forwarding, session reuse, three independent anonymous clients requesting the exact authenticated URLs, and logout with access returning to 401. All redirects stayed on the CloudFront HTTPS hostname; no cached authenticated content/cookies reached anonymous clients.
- P05 browser acceptance: on-instance headless Chromium rendered AdminCentral's Pages and Assets apps and the Travel page/images, reused the session through navigation/reload, kept a separate context anonymous, and restored login after logout and subsequent access. All document requests stayed on CloudFront HTTPS with no ALB URLs, HTTP asset URLs, mixed-content errors, JavaScript page errors, or unexpected destinations. Chromium reported Secure, HttpOnly, `/magnoliaAuthor`, and SameSite=Lax on the session cookie. The browser guard blocked three optional external HTTPS font/widget services (`fonts.googleapis.com`, `cdn.jsdelivr.net`, `static.addtoany.com`); those services remain untested, while local content/images passed. Only sanitized screenshots and results leave EC2; no trace, HAR, video, persistent profile, or cookie-state file is produced.
- P05 final infrastructure check: AWS MCP confirmed distribution `E178D8X4DHIIP9` Deployed and the replacement ALB target healthy after authenticated tests. The final drift plan in ignored `build/p05/final-drift-plan.txt` exited 0 with no changes. P05 acceptance criteria pass; P06 remains Ready, and P07's P05 dependency is satisfied while P06 remains outstanding. No P05 blocker remains. Remote-state migration, CI, and publication were not started; the stack stays running at this review checkpoint.
- P05 evidence and test tooling: the browser checker uses Playwright 1.64.0 and a nonpersistent headless Chromium context, with all credential handling on EC2. The sanitized AdminCentral screenshot is `docs/evidence/p05-admincentral.jpg`. Temporary browser tooling and screenshot staging are separate from application provisioning and are removed after evidence export; package support libraries do not change the proxy/application configuration.
- P05 checkpoint review: inspected the final browser helper, README/plan changes, and sanitized screenshot. The final helper passed using DOM/application readiness checks; temporary browser tooling, browser downloads, and screenshot staging were removed. AWS MCP confirmed the target still healthy afterward. Python compilation, Terraform formatting, whitespace, local documentation links, sensitive-content patterns, and local-state/artifact ignore checks passed. The verification commit records P05 as Verified without changing Terraform or the deployed application after the implementation commit.
- P05 independent review: checked implementation commit `9e9ea00` and verification commit `ff3ba22` from a clean working tree. Reviewed CloudFront, ALB ingress, Nginx forwarding/caching, both verification helpers, recorded authenticated/browser results, and the sanitized screenshot. Formatting, Python compilation, whitespace, archive integrity/version checks, repeatable transforms, and provisioning rendering/syntax checks passed. Re-ran the anonymous CloudFront checker successfully for HTTPS redirects, readiness, uncached errors, login assets, cookie attributes, and protocol spoof handling. Live AWS MCP checks confirmed the expected distribution Deployed, its origin/method/error-TTL settings, and the replacement target healthy. A fresh drift plan in ignored `build/p05/review-drift-plan.txt` exited 0 with no changes. Authenticated tests were reviewed from P05 evidence without reading credentials or repeating them. No blocking findings; documented HTTP-origin and prefix-list limitations remain. P06 is next.

- P06 publication: created the public repository `amanya/Crescendo-DevOps-exam` (GitHub owner type User, owner ID `4490611`, repository ID `1420637563`) after source/history review. Preserved P05's independent review in commit `4c7543f`, which also establishes the trusted reusable workflow on `main`. The P06 implementation branch is `codex/p06-state-and-ci`; [PR #1](https://github.com/amanya/Crescendo-DevOps-exam/pull/1) remains open.
- P06 bootstrap: applied a reviewed plan containing only eight new backend/CI identity resources. AWS MCP verified bucket `crescendo-exam-tfstate-317399646022-eu-central-1` private, all public-access blocks enabled, versioning Enabled, BucketOwnerEnforced ownership, TLS deny policy, and default SSE-S3/AES256. No existing GitHub OIDC provider was present; bootstrap created it and role `arn:aws:iam::317399646022:role/crescendo-exam-github-plan`. Bootstrap state remains separate/local, mode `0600`, with a private versioned recovery copy at `bootstrap/terraform.tfstate`; the README records recovery and teardown order.
- P06 migration: made a mode-`0600` backup under ignored mode-`0700` `build/p06/backups/`, then used `terraform init -migrate-state -force-copy`. IDs migrated unchanged, but verification detected changed snapshot metadata. With no concurrent writers, preserved the migrated snapshot, proved equality of every nonmetadata state field, and restored the original snapshot with the documented guarded `terraform state push -force` recovery. Final lineage and all 33 managed IDs match the original; serial advanced 41 -> 42. A new remote-state plan exited 0 with no changes. EC2 remains `i-03e2b17589905593d`, CloudFront remains `E178D8X4DHIIP9` Deployed, and its ALB target is healthy. The anonymous CloudFront checker passed readiness 200, redirects, uncached errors, login assets, cookie flags, and protocol-spoof handling. No workload apply or CMS change occurred.
- P06 authentication/CI: removed the provider's hardcoded profile; local operators use `AWS_PROFILE=default`, and CI uses OIDC environment credentials. Repository variables `AWS_PLAN_ROLE_ARN`, `TF_STATE_LINEAGE`, and `TF_STATE_IDENTITIES_SHA256` are configured. Trust requires immutable repository/owner IDs, PR context, the reusable workflow on `main`, and audience `sts.amazonaws.com`. Both caller and trusted reusable workflow reject fork/Dependabot PRs before AWS access. Formatting and backend-disabled validation cover both Terraform roots. Planning reads only workload state, can manage only its lock object, checks lineage/IDs, handles exit codes 0/2/failure, and publishes only sanitized counts. The actual PR confirmed the exact configured subject/audience, assumed the OIDC role, read remote state, and matched lineage/all 33 IDs. The first plan exposed four missing/mismatched read permissions; the bootstrap policy was corrected without workload changes. The corrected role passed the full remote-state plan; final evidence follows below.

- P06 additional checks: bootstrap recovery download matched local state byte for byte. Both Terraform roots validate; local bootstrap and workload plans exit 0. Workflow YAML/Bash syntax passed, and a stubbed Terraform command proved exit 0/2 succeed while exit 1 fails. Added official signed Linux provider checksums after the first PR run exposed a platform checksum gap. IAM simulation allowed state reads/lock writes and denied state writes/deletes, bootstrap reads, instance termination, PassRole, and SSM commands. Main requires both named CI checks and one review, dismisses stale reviews, and disallows force pushes/deletion; admin bypass remains available. No fork PR has been executed; its denial is established by the trusted reusable gate and exact workflow-bound IAM subject.

- P06 final validation: [PR #1](https://github.com/amanya/Crescendo-DevOps-exam/pull/1) and [workflow run 38732314501](https://github.com/amanya/Crescendo-DevOps-exam/actions/runs/38732314501) passed `Format and validate` and `Trusted PR / Remote state plan` at source commit `873a15f`. The credential-free job formatted and validated both roots. The trusted job confirmed the actual customized subject/audience, obtained short-lived OIDC credentials, read the migrated state, verified the original lineage/all 33 managed IDs, and produced plan exit 0 with `{'no-op': 33}`. No workload recreation or mutation was proposed. The fifth provider-discovered read, `ec2:DescribeInstanceTypes`, was added under the existing regional condition. Final CloudFront policy reads target exact live IDs in the caller-account namespace, verified by CI; prefix-list entry reads target the exact AWS-managed list. Repository secret count is zero; only the three documented nonsecret variables are configured.
- P06 checkpoint: final bootstrap plan exited 0; its latest state was archived to the separate private versioned key. Both roots validate, formatting/whitespace and tracked-source credential-pattern checks pass, and state/plans/caches/backups remain ignored. The published screenshot was visually checked and contains no credential material. S3 object metadata confirms SSE-S3/AES256 for both workload and bootstrap snapshots. Existing workload IDs and application health remain intact. Remaining limits: bootstrap changes/recovery are manual; state versions need eventual operator cleanup; a live fork PR was not exercised; main admins can bypass branch protection; state recovery does not restore CMS content. Existing single-instance, HTTP-origin, and application-backup limits remain. P06 is Verified, P07 is Ready, and the next task after review is P07 lifecycle/submission work. Leave PR #1 open; no invitations, teardown, or P07 lifecycle changes were made.

- Post-P06 visibility change (2026-10-15): the user requested a private repository. GitHub confirmed `PRIVATE` for `amanya/Crescendo-DevOps-exam`; Actions remains enabled and the custom OIDC settings/immutable repository IDs are unchanged. Saved the previous main protection settings under ignored `build/p06/protection-before-private.json`. GitHub now returns HTTP 403 for branch protection: “Upgrade to GitHub Pro or make this repository public to enable this feature.” Required-review/check enforcement is unavailable on this private repository's current plan; use manual review and check inspection until a supported plan is enabled. The workflow's fork gate and read-only AWS role remain in place. No paid plan change, AWS change, collaborator invitation, or merge was performed. [Private-repository run 38733705991](https://github.com/amanya/Crescendo-DevOps-exam/actions/runs/38733705991) passed formatting/validation and trusted OIDC planning, verified the original lineage/all 33 managed IDs, and reported plan exit 0 with 33 no-op actions. The anonymous CloudFront checker also passed readiness 200, redirects, assets, and cookie/protocol checks. PR #1 remains open; the next task after review is P07. P07 must confirm submission access while preserving the user's private-visibility preference.
