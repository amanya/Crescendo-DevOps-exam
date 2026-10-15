# Crescendo DevOps exam: plan and progress

Updated: 2026-10-15 (Europe/Madrid)

## Current position

P01 is Verified. Git is initialized on `main` with an initial local commit. Terraform 1.16.6 is installed, and the minimal configuration has initialized with AWS provider 6.69.0. Formatting, validation, ignore-rule checks, and the sensitive-content review passed.

P01 review passed. P02 is Verified against its preparation criteria: the official Magnolia CE package is downloaded and pinned, compatibility is checked, and the provisioning templates pass local checks. The P02/P03 interface is recorded below. EC2 execution and all application runtime claims remain pending P04. EC2 size and origin encryption remain undecided. No infrastructure has been deployed.

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
- Submit the public repository and CloudFront screenshots or video, send the requested collaborator invitations, and prepare for the walkthrough.
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
| P03 | VPC, EC2, and ALB | Ready | P01 | Unassigned |
| P04 | Application integration | Queued | P02, P03 | Unassigned |
| P05 | CloudFront | Queued | P04 | Unassigned |
| P06 | Remote state and PR checks | Queued | P01, P03 | Unassigned |
| P07 | Lifecycle and submission | Queued | P04, P05, P06 | Unassigned |

### P00: AWS access

- AWS MCP `STS.GetCallerIdentity` succeeded for account `317399646022` and user `amanya-crescendo`, with `eu-central-1` selected.
- Authentication works. We still need to check permissions for the deployment operations.

### P01: Repository and tooling

- Initialize Git and ignore Terraform state, local configuration, generated artifacts, and secrets.
- Install Terraform, record Terraform/provider version constraints, and commit the provider dependency lock file.
- Create directories as their files are needed and start the README.

Done when Git is initialized, ignore rules protect local configuration/state/artifacts/secrets while retaining the provider lock file, Terraform is installed, minimal Terraform/provider configuration uses profile `default` and region `eu-central-1`, local initialization generates the lock file, and the README explains purpose, prerequisites, setup, and deployment status. Formatting, validation, and a sensitive-content review must pass before the initial local commit. Remote state, resource creation, CI, and publication remain in later tasks.

Verified on 2026-10-15; validation evidence is recorded below. P03's P01 dependency is satisfied. Agree on the P02/P03 application interface before parallel implementation; P06 remains Queued until P03 is verified.

### P02: Application provisioning

- Choose a Community Edition artifact we can download, pin its version, and check which Java/Tomcat versions work with it.
- Work out first-run initialization, application paths, and embedded persistence settings.
- Write readable bootstrap, Nginx, and systemd configuration. Make installation and startup failures visible in the logs.
- Before infrastructure work proceeds in parallel, agree on the Nginx target port, Magnolia context path, readiness check, and Terraform template inputs.

Done when we've checked artifact access and version compatibility and have an installation procedure ready to deploy. P04 checks that it runs on EC2.

Verified on 2026-10-15 for those preparation criteria; evidence is recorded below. This checkpoint stops before P03 infrastructure work. Runtime acceptance remains with P04.

### P02/P03 interface

P02 owns `infra/templates/bootstrap.sh.tftpl`, `infra/templates/nginx.conf.tftpl`, `infra/templates/magnolia.service.tftpl`, and the local checker `scripts/check-provisioning.py`. The primary agent maintains README and plan changes. No other agent was dispatched. P03 can use this interface without changing the application templates:

| Item | Contract |
| --- | --- |
| Magnolia | CE Travel Demo 6.3.27, official public Nexus ZIP linked from [Magnolia's 6.3 releases](https://docs.magnolia-cms.com/product-docs/6.3/releases/); exact URL and SHA-256 are in README and bootstrap |
| Artifact pin | SHA-256 `8ba8ea6bcaffb7c6f6895d2ed024e322bfed546f6e475c710018b7a3b16b1a99`; top directory `travel-demo-community-webapp-6.3.27/apache-tomcat-9.0.121` |
| Runtime | Bundled Tomcat 9.0.121; Ubuntu `openjdk-17-jre-headless`, Java home `/usr/lib/jvm/java-17-openjdk-amd64`; keep repository patch updates |
| OS and CPU | Ubuntu Server 24.04 LTS with cloud-init/systemd, x86_64 (`amd64`). Bootstrap rejects another release or architecture. P03 selects the AMI |
| Sizing | Heap `-Xms256m -Xmx2048m`; allow at least 4 GiB RAM. P03 still chooses instance and root-disk sizes; P04 checks memory and disk use |
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

P04 must verify apt installation and the native systemd unit, first-run modules and administrator setup without browser intervention, initialized sample content and private login, readiness returning 200 only after initialization, unhealthy responses while Magnolia is stopped or failing, service recovery, ALB registration, and HTTP redirects/assets/sessions. Check a reboot reuses the data paths and credentials; P07 records the full content-retention and instance-replacement demonstration. Do not paste credential values or unsanitized application logs into evidence. Browser HTTPS and the forwarded protocol through CloudFront remain P05 checks.

P02 limitations: no EC2 execution; Java/Nginx patch versions follow apt repositories; the ZIP checksum is locally calculated from an official HTTPS download without a separate vendor signature; embedded H2, one author webapp, one disk, and no content backup remain deliberate exam limits. The local installation checker does not prove application readiness, reboot persistence, or successful recovery.

### P03: Infrastructure

- Build the required VPC layout and routing, one NAT Gateway, security groups, private EC2 instance, ALB, and target group.
- Delete the root disk on termination and use the default encryption behavior.
- Configure Systems Manager access and pass the bootstrap script through user data.
- Add useful outputs and explain the availability limits of using one instance and one NAT Gateway.

Done when formatting and validation pass, the Terraform plan matches the agreed architecture, and the code is ready to deploy.

### P04: Application integration

- Apply the infrastructure and inspect bootstrap and service logs.
- Check installation, service startup, and target registration. ALB health checks must reflect whether Magnolia is available.
- Check that Magnolia is ready to serve requests. Terraform apply completing doesn't confirm application readiness.

Done when a fresh instance installs and configures Magnolia automatically, completes first-run setup, and serves it through the ALB.

### P05: CloudFront

- Configure the ALB origin, browser HTTPS, and an explicit origin connection policy.
- Start with caching disabled and forward what the application needs for its sessions and requests.
- Check pages, static assets, redirects, and login/session behavior through CloudFront.

Done when Magnolia works in a browser through the CloudFront URL and we've documented the origin encryption choice and its limitations.

### P06: State and CI

- Set up protected remote Terraform state. Document how to bootstrap it, migrate state, and clean it up.
- Configure repository-scoped AWS OIDC access for trusted PR planning.
- Run `terraform fmt -check`, `terraform validate`, and `terraform plan` on PRs.
- Decide how to handle untrusted/fork PRs without giving them AWS access. Keep deployment manual for the first version.

Done when an actual PR passes the checks and produces a real plan against the intended state.

### P07: Verification and submission

- Create content, reboot the instance, and check that the content survives.
- Replace only the instance through Terraform. Check that provisioning runs automatically and a fresh CMS loads through the same CloudFront distribution.
- Finish the README: architecture, prerequisites, commands, configuration, troubleshooting, limitations, and teardown.
- Capture CloudFront screenshots/video and prepare walkthrough notes.
- Publish the public `Crescendo-DevOps-exam` repository and invite `tristanamargo-crescendo` and `jeremysummers` as part of submission preparation.

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
- No current P01/P02 preparation blocker. P02's runtime checks and deployment permissions remain unverified for later tasks. Next: review this local P02 commit, then start P03 using the recorded interface when requested. Stop at this checkpoint.
