# Crescendo DevOps exam

Deploy Magnolia Community Edition on AWS with Terraform for the Crescendo DevOps exam. The request path is browser -> CloudFront -> ALB -> Nginx -> Tomcat/Magnolia on one private EC2 instance.

## Current status

P01 through P06 are Verified. CloudFront serves Magnolia at the HTTPS URL below in account `317399646022`, region `eu-central-1`. On 2026-10-15, authenticated browser and HTTP checks passed for login, CSRF protection, AdminCentral, Travel content/assets, session reuse, anonymous isolation, and logout. The ALB target is healthy, CloudFront is Deployed, and the final Terraform plan reports no changes. P06 migration and actual PR checks passed against remote state. P07 is Ready; the P06 PR remains open for review. The P05 instance replacement intentionally started a fresh CMS.

The infrastructure uses two public and two private subnets across two availability zones, one NAT Gateway, and one private EC2 instance. The OS, software, and CMS data share one EBS root volume, deleted on termination. Instance replacement reinstalls the application and starts a fresh CMS. EBS encryption follows the AWS account and AMI defaults.

See [the plan](docs/plan.md) for scope, acceptance criteria, validation evidence, and the complete P02/P03 interface.

## Prerequisites

- Git. Local setup was checked with Git 2.50.1.
- Terraform 1.16.6 or a newer 1.16 patch release. The configuration restricts Terraform to `~> 1.16.6`.
- AWS CLI v2 for local AWS access and recovery. Version 2.35.13 is installed locally. The intended AWS profile is `default`, and the workload region is `eu-central-1`.
- Network access to the [Terraform Registry](https://registry.terraform.io/providers/hashicorp/aws) and HashiCorp's provider downloads during initialization.
- Python 3 for the local provisioning checker. ShellCheck is optional; the checker runs it when available.

GitHub CLI 2.95.0 is installed locally. Formatting and validation need no AWS credentials when initialization uses `-backend=false` in a fresh Terraform data directory. Normal initialization, planning, and deployment access the S3 backend and need AWS authentication. Use the local `default` profile and keep credential material in your normal AWS configuration, outside this repository.

## Local setup

Install Terraform using [HashiCorp's installation instructions](https://developer.hashicorp.com/terraform/install). On macOS with Homebrew:

```sh
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
terraform version
```

The verified local version is Terraform 1.16.6 for macOS arm64. HashiCorp's official [release metadata](https://releases.hashicorp.com/terraform/index.json) and [AWS provider metadata](https://registry.terraform.io/v1/providers/hashicorp/aws) listed Terraform 1.16.6 and AWS provider 6.69.0 when P01 was completed on 2026-10-15. The constraints allow patch updates within those minor releases; `infra/.terraform.lock.hcl` records the selected provider version and checksums.

From the repository root, initialize and check the configuration:

```sh
AWS_PROFILE=default terraform -chdir=infra init -input=false -lockfile=readonly
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
```

Initialization downloads the pinned provider and connects to the existing S3 backend. It does not create AWS resources. On a new account, create the backend with `bootstrap/` first; see the state instructions below. Commit both provider lock files after an intentional dependency update; follow the [HashiCorp lock-file guidance](https://developer.hashicorp.com/terraform/language/files/dependency-lock).

The `.gitignore` excludes local state, plans, provider downloads, variable files, environment files, credentials, and generated application artifacts. It keeps `.terraform.lock.hcl` tracked. Review files before committing them; ignore patterns cannot detect every sensitive value.

## Repository layout

```text
AGENTS.md                   Project instructions
README.md                   Purpose, prerequisites, and local setup
docs/plan.md                Scope, task status, and validation evidence
infra/versions.tf           Terraform and AWS provider constraints
infra/providers.tf          AWS credential chain, region, account guard, and tags
infra/backend.tf            S3 workload state and native locking
bootstrap/main.tf           Separate state bucket and GitHub OIDC identity
bootstrap/.terraform.lock.hcl  Bootstrap provider selection and checksums
.github/workflows/terraform.yml       PR formatting, validation, and plan caller
.github/workflows/terraform-plan.yml  Trusted reusable plan workflow on main
infra/variables.tf          Reviewed Ubuntu AMI release input
infra/network.tf            VPC, subnets, Internet Gateway, NAT, and routing
infra/compute.tf            AMI, instance role/profile, security group, and EC2
infra/load-balancer.tf      ALB security group, listener, target, and health check
infra/cloudfront.tf         Distribution, disabled caching, forwarding, and security headers
infra/outputs.tf            HTTPS endpoints, resource IDs, and origin hostname
infra/.terraform.lock.hcl   Provider selection and checksums
infra/templates/           Bootstrap, Nginx site, and Magnolia systemd unit
scripts/check-provisioning.py  Local template and archive checks
scripts/check-runtime.py       Sanitized on-instance diagnostics
scripts/check-private-login.py  SSM/loopback login, content, and session checks
scripts/check-cloudfront.py     Sanitized public HTTPS and on-instance session checks
scripts/check-cloudfront-browser.py  On-instance headless browser acceptance checks
```

## Infrastructure and sizing

Local operators select profile `default` through `AWS_PROFILE=default`. Terraform uses the standard AWS credential chain in `eu-central-1` and refuses accounts other than `317399646022`. Resources carry `Project=crescendo-devops-exam` and `ManagedBy=Terraform` tags where supported. The workload uses versioned S3 state with native locking; the bootstrap has separate local state and a private S3 recovery copy.

| Component | Configuration |
| --- | --- |
| VPC | `10.42.0.0/16`, with DNS support and hostnames enabled |
| Zone `eu-central-1a` | Public `10.42.0.0/24`; private `10.42.10.0/24` |
| Zone `eu-central-1b` | Public `10.42.1.0/24`; private `10.42.11.0/24` |
| Public routing | Both public subnets share a route table with `0.0.0.0/0` to the Internet Gateway |
| Private routing | Both private subnets share a route table with `0.0.0.0/0` to one public NAT Gateway and Elastic IP in public subnet `a` |
| EC2 | One `t3.medium` in private subnet `a`, no public IP or SSH key, IMDSv2 required |
| Root disk | One 30 GiB gp3 EBS volume for all software and data; deleted on termination; no explicit encryption or KMS override |
| ALB | Internet-facing IPv4 ALB in both public subnets; HTTP listener and instance target on port 80; idle timeout 120 seconds |
| Health | GET `/magnoliaAuthor/.rest/health/ready`; matcher `200` only; interval 30 seconds, timeout 5 seconds, healthy threshold 2, unhealthy threshold 3 |

The official Ubuntu Server 24.04 LTS amd64 AMI comes from Canonical owner `099720109477`, using the name format in [Canonical's image lookup instructions](https://ubuntu.com/aws/docs/aws-how-to/instances/find-ubuntu-images/). The only input, `ubuntu_ami_name`, defaults to the exact release `ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20261004`. AWS MCP and the real plan resolved it to `ami-0e27250725fa51794`. Pinning the release prevents a newly published image from silently replacing the instance and deleting CMS data. Review any AMI input update as a destructive instance replacement.

`t3.medium` has 2 vCPUs and 4 GiB RAM, meeting the P02 minimum while leaving memory outside the 2 GiB Java heap for the OS, Nginx, and JVM overhead. It uses standard CPU credits to avoid surplus-credit charges; sustained CPU load can throttle it, including first-run initialization. The 30 GiB gp3 root disk is a starting size for the demo, with space beyond the AMI's 8 GiB minimum for package extraction, repository growth, and logs. The first healthy run used about 953 MiB of JVM cgroup memory (1,775 MiB peak), with about 2,409 MiB available RAM and 25.20 GiB free disk. Tomcat reported 407 seconds for initial startup; cloud-init and both services completed about nine minutes after launch. CloudWatch showed a zero credit balance and roughly 20% CPU use during initialization, with zero surplus credits charged. Idle periods then earned credits and later startup consumed them. These measurements confirm the expected standard-mode behavior; no workload capacity test was performed.

The ALB security group accepts TCP 80 only from AWS's managed CloudFront origin-facing prefix list and sends TCP 80 only to the instance security group. The instance accepts TCP 80 only from the ALB security group and permits outbound TCP 80/443 for Ubuntu packages, Magnolia, and Systems Manager through NAT. The VPC resolver provides DNS. There is no inbound rule for SSH or Tomcat; the existing template binds Tomcat to `127.0.0.1:8080`. Browser traffic uses HTTPS to CloudFront. CloudFront-to-ALB and ALB-to-Nginx traffic use unencrypted HTTP. Direct browser access to the ALB is blocked by its security group. The prefix list admits CloudFront origin traffic generally, rather than identifying this distribution; distribution-specific origin authentication remains a limitation.

The instance profile trusts EC2 and attaches only `AmazonSSMManagedInstanceCore`. Ubuntu Server 24.04 images [include SSM Agent](https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html); P04 confirmed agent `3.3.4793.0` running and the node Online. Its HTTPS connections use NAT, so this configuration needs no VPC endpoints or inbound management ports. Human operators separately need Systems Manager session permissions and either the AWS console or the CLI Session Manager plugin. Session output logging is not configured here.

EC2 explicitly depends on both default routes, all public/private route-table associations, its security-group rules, and the SSM policy attachment. The NAT Gateway also waits for public routing. This makes Terraform establish the outbound path before cloud-init downloads packages or Magnolia. It does not prove the remote repositories or application are available at runtime.

## Plan review and deployment prerequisites

The checked configuration requires no variable file. Planning needs STS identity access, EC2 image/managed-prefix-list lookup permissions, and CloudFront managed-policy read permissions. The deployer must also be able to create, read, tag, update, and delete the planned EC2/VPC, Elastic IP/NAT, ELBv2, IAM, and CloudFront distribution/request-policy resources, attach the SSM managed policy, and pass the instance role to EC2. Elastic Load Balancing may need permission to create its service-linked role if it is absent. A successful plan does not verify these write permissions or available quotas/capacity.

Before a new deployment, confirm capacity and quotas for a VPC, four subnets, one NAT Gateway/Elastic IP, an ALB/target group, and a 2-vCPU on-demand instance. Keep the chosen AMI available, the Ubuntu repositories and `nexus.magnolia-cms.com` reachable, and CloudFront origin-facing TCP 80 reachable at the ALB. CloudFront uses its default hostname and certificate, so no customer certificate or domain is required. There is no application secret input. The backend and GitHub planning role are managed separately in `bootstrap/`.

To prepare a fresh plan, run from the repository root:

```sh
mkdir -p build/p05
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
python3 scripts/check-provisioning.py
AWS_PROFILE=default terraform -chdir=infra plan -input=false -out=../build/p05/deploy.tfplan
terraform -chdir=infra show ../build/p05/deploy.tfplan
```

P04 generated and inspected a fresh plan against the current account and local state, then applied the saved plan with 31 creations and no updates/deletions. It checked quotas and IAM permissions first. Before any later apply, review the root-volume lifecycle, routing and dependencies, security-group references, health settings, and rendered user data. P05 renders 9,858 bytes of user data, below EC2's 16 KiB limit; the Nginx template changes intentionally replace the instance. Generated plans, logs, rendered files, and state remain ignored; do not commit them.

After reviewing the saved plan, apply that exact file:

```sh
terraform -chdir=infra apply ../build/p05/deploy.tfplan
terraform -chdir=infra output
```

Preserve `infra/terraform.tfstate` and its backup locally until P06 migrates them. Losing state does not remove the running resources. `alb_dns_name` identifies the CloudFront origin. The `cloudfront_distribution_id`, `cloudfront_url`, `author_url`, and `readiness_url` outputs identify the deployed distribution and public HTTPS endpoints. Terraform finishing an apply does not confirm cloud-init or application readiness.

## Running development stack

| Item | Deployed value |
| --- | --- |
| Author | [Magnolia login](https://d2xpkbus8fu2t7.cloudfront.net/magnoliaAuthor/) |
| Readiness | [Magnolia readiness](https://d2xpkbus8fu2t7.cloudfront.net/magnoliaAuthor/.rest/health/ready), exact HTTP 200 when ready |
| CloudFront | `E178D8X4DHIIP9`, [distribution console](https://us-east-1.console.aws.amazon.com/cloudfront/v4/home?region=us-east-1#/distributions/E178D8X4DHIIP9) |
| Instance | `i-03e2b17589905593d`, private `10.42.10.237` |
| Root volume | `vol-0507e0dd3d123a7d3`, 30 GiB gp3, deleted on termination; unencrypted under the current account/AMI defaults |
| VPC | `vpc-0dae6a3137091be57` |
| NAT Gateway | `nat-083d0e0c9070b58d4`, EIP `18.195.185.6` |
| ALB | `arn:aws:elasticloadbalancing:eu-central-1:317399646022:loadbalancer/app/crescendo-exam/5836054be05d28c9` |
| Target group | `arn:aws:elasticloadbalancing:eu-central-1:317399646022:targetgroup/crescendo-exam-magnolia/b2a5f934ec75e3ed` |
| Security groups | ALB `sg-0d2eb879407ba8780`; instance `sg-0b53b8f372914cf56` |

The CloudFront author page returns HTTP 401 with Magnolia's login form until authenticated. `/` and `/magnoliaAuthor` redirect to `/magnoliaAuthor/`; the login CSS and images return 200 through CloudFront and the ALB. Readiness is unauthenticated and returns 200 only after the `magnolia-instance`, `datastore`, and `admin-setup` checks are UP. Use only the CloudFront HTTPS URL for browser login. The ALB HTTP URL is an origin, not a browser entry point.

P04 used AWS MCP Systems Manager Run Command to run `scripts/check-runtime.py` on the instance as root. It prints service/package/health results and resource measurements, and summarizes log markers without returning arbitrary log lines. The private login helper, `scripts/check-private-login.py`, runs only against loopback Nginx. It reads the local password into memory, submits the CSRF-protected form, checks session rotation and authenticated content, then logs out. Run it only in an authorized private SSM context; never paste credentials, cookies, response HTML, or unsanitized logs into evidence. The user authorized this local-file workflow as a P04 exception to the Secrets Manager/`asm-exec` rule after the required secret skill was loaded. No Secrets Manager resource or additional IAM access was added.

P04 private checks passed for administrator login, AdminCentral, the initialized Travel page and REST node, six referenced content assets, and 95 installed modules. Login rotated the session; subsequent requests reused it, and logout restored HTTP 401. The session cookie was HttpOnly with path `/magnoliaAuthor`; Secure was false over local HTTP. Credentials and session cookies were never sent over the public HTTP connection. After reboot, private checks confirmed the same repository/sample identifier and password file, then repeated login, content, assets, sessions, and logout successfully. P07 owns the full content-retention and replacement demonstration.

## CloudFront and HTTPS

CloudFront uses the existing ALB as a custom origin, `PriceClass_100`, pay-as-you-go pricing, the assigned `cloudfront.net` hostname, and its default certificate. Viewer HTTP requests redirect to HTTPS. The development origin policy is explicitly `http-only` on port 80: TLS terminates at CloudFront, so HTTPS in the address bar does not mean the origin connection is encrypted. HTTPS to the ALB would require a trusted origin certificate and a suitable domain; this exercise does not provision either. Nginx-to-Tomcat is HTTP on loopback. The default CloudFront certificate also retains AWS's default TLS security policy.

The managed `CachingDisabled` policy sets minimum, default, and maximum TTLs to zero. A custom origin request policy forwards every viewer header (including Host, Authorization, Origin, Referer, and application CSRF headers), all cookies, and all query strings, plus CloudFront's generated viewer-protocol header. All seven supported HTTP methods are allowed, with request bodies forwarded normally. No path has a cache override. Custom error TTLs are zero for every configurable error status, without rewriting status codes or bodies. Nginx sends `Cache-Control: no-store, private` on application responses, readiness, redirects, and errors, replacing upstream cache directives. Browser caches and intermediary caches must not retain author responses or session cookies.

Tomcat's loopback-only RemoteIpValve uses the restored viewer protocol to mark HTTPS requests secure and generate public HTTPS redirects and Secure session cookies. Magnolia keeps its login/session and CSRF handling. The managed CloudFront `SecurityHeadersPolicy` supplies HSTS, same-origin framing, content-type, and other browser headers. A new Content Security Policy is deferred because Magnolia's admin UI and previews need application-specific testing.

CloudFront access logs, WAF/rate rules, a private VPC origin, distribution-specific origin authentication, and origin TLS are outside this small development deployment. CloudFront's managed address restriction reduces direct origin exposure but does not make the HTTP origin encrypted or bind it to a single distribution. Nginx has local access/error logs; CloudFront request logging and alerting are not configured. Keep these limits in mind before using real content or opening the environment to more users.

P05 anonymous verification passed for HTTP-to-HTTPS redirects, relative Nginx root/context redirects, the exact 200 readiness response, repeated uncached 404s, the 401 login page, and three referenced login assets. The CSRF cookie is Secure and HttpOnly with path `/magnoliaAuthor`; spoofing viewer forwarding headers did not downgrade it. The browser rendered the styled login form over HTTPS and recovered from the startup 502 at the same URL. The ALB target is healthy, direct public ALB HTTP access times out under the prefix-list rule, and the post-deployment Terraform plan exits 0 with no changes. The approved on-instance authenticated HTTP check also passed CSRF rejection, login with a new session, AdminCentral, Travel page/node, six sample assets, module queries, session reuse, three independent anonymous clients, and logout. The exact authenticated URLs stayed inaccessible to anonymous clients, with no reused authenticated cookies or cache hits.

To repeat the anonymous check:

```sh
python3 scripts/check-cloudfront.py "$(terraform -chdir=infra output -raw cloudfront_url)"
```

`--authenticated` is restricted to an explicitly approved on-instance SSM run. It reads the local password in memory and submits it only to the verified CloudFront HTTPS hostname. Do not run it on a workstation or export credentials/cookies to perform the test. The user explicitly extended the P04 exception for P05 to this verified CloudFront HTTPS destination, with credentials/cookies held in memory on EC2 and only sanitized evidence returned. This does not authorize exporting them to a workstation or submitting them elsewhere. The checker returns sanitized status/count/attribute evidence and suppresses response bodies and exception messages.

The on-instance headless Chromium check, `scripts/check-cloudfront-browser.py`, passed with Playwright 1.64.0. It rendered AdminCentral's Pages and Assets apps, displayed Travel content and images, retained the session across page navigation and reload, kept a separate browser context anonymous, and returned to login after logout and a subsequent request. Every document navigation stayed on the CloudFront HTTPS hostname. It found no HTTP asset URLs, ALB URL leaks, mixed-content errors, or JavaScript page errors. Chromium reported the session cookie as Secure, HttpOnly, path `/magnoliaAuthor`, and SameSite=Lax.

The browser test permits network requests only to this stack's CloudFront HTTPS origin. It intentionally blocked optional Travel-demo assets at `fonts.googleapis.com`, `cdn.jsdelivr.net`, and `static.addtoany.com`; those third-party fonts/widgets were not verified. Local sample content and images rendered successfully. The checker fails on any unexpected destination, HTTP downgrade, or document navigation outside the approved origin. No tracing, video, HAR, persistent browser profile, or cookie-state export is enabled. Playwright/Chromium are temporary test tooling, not part of provisioning; an approved repeat run needs those tools on the instance.

A [sanitized AdminCentral screenshot](docs/evidence/p05-admincentral.jpg) records the rendered app launcher after CloudFront HTTPS login. It contains no credentials, cookies, or tokens.

## Application installation

The bootstrap expects Ubuntu Server 24.04 LTS, x86_64 (`amd64`), with cloud-init, systemd, and working Ubuntu package repositories. Terraform selects a matching Canonical AMI, pinned to the reviewed release above. It installs Ubuntu's `openjdk-17-jre-headless` and Nginx packages, retaining their repository patch updates. The JVM has a 2 GiB maximum heap. The selected `t3.medium` supplies 4 GiB RAM, and its 30 GiB root disk leaves room for the OS, installation staging, CMS data, and logs. Measured startup memory, disk use, and timing are recorded above.

The application is the official [Magnolia CE Travel Demo 6.3.27 Tomcat bundle](https://nexus.magnolia-cms.com/repository/magnolia.public.releases/info/magnolia/demo/travel-demo-community-webapp/6.3.27/travel-demo-community-webapp-6.3.27-tomcat-bundle.zip), linked from Magnolia's [6.3 releases](https://docs.magnolia-cms.com/product-docs/6.3/releases/). P02 downloaded the complete 251,521,274-byte ZIP anonymously with HTTP 200, checked its ZIP integrity, and inspected Magnolia core 6.3.27 and Tomcat 9.0.121 inside it. The bootstrap checks this locally calculated SHA-256 before extraction:

```text
8ba8ea6bcaffb7c6f6895d2ed024e322bfed546f6e475c710018b7a3b16b1a99
```

The exam links to Magnolia 6.2 documentation. This installation uses the 6.3 stack: Magnolia's [6.3 certified stack](https://docs.magnolia-cms.com/performance-tuning/6.3/system-requirements/certified-stack/) specifies Java 17 as its build baseline and recommends Tomcat 9. Apache's [Tomcat compatibility table](https://tomcat.apache.org/whichversion.html) lists Tomcat 9 with Servlet 4.0 and Java 8 or later. The selected Java 17/Tomcat 9 combination matches those requirements. Ubuntu supplies [OpenJDK 17 for Noble amd64](https://packages.ubuntu.com/en/noble/openjdk-17-jre-headless); its [file list](https://packages.ubuntu.com/noble-updates/amd64/openjdk-17-jre-headless/filelist) confirms the configured Java home. The bundle supplies Tomcat, avoiding the distribution's separate Tomcat package.

The bootstrap installs one author webapp at `/opt/magnolia/webapps/magnoliaAuthor`. It runs `catalina.sh run` under the `magnolia` system user, bypassing the bundle launcher that would create a second public webapp. The demo content remains available on the author instance; publishing to a separate public instance is outside this deployment.

Automatic module installation uses `magnolia.update.auto=true`. Magnolia 6.3.27 also requires [initial administrator setup](https://docs.magnolia-cms.com/product-docs/6.3/administration/security/set-superuser-password/). The script generates a random initial password directly into `/etc/magnolia/superuser-password`, owned by `root:magnolia` with mode `0640`, and configures Magnolia's file-based bootstrap option. It disables interactive fallback and keeps the administrator readiness check enabled. Values never appear in template inputs or bootstrap output. P04 verified initial login privately through SSM without emitting the password. These bootstrap settings apply only to initial setup; changing the file after setup does not rotate the account password.

The [Magnolia configuration reference](https://docs.magnolia-cms.com/product-docs/6.3/administration/architecture/configuration-management/) explains the installation and path properties. `magnolia.home` stays at the webapp root because the demo uses it to locate its bundled modules and author configuration. Mutable data uses these root-disk paths:

| Path | Contents |
| --- | --- |
| `/var/lib/magnolia/repositories` | Jackrabbit repository, embedded H2 databases, indexes, and file datastore |
| `/var/lib/magnolia/cache`, `/var/lib/magnolia/tmp`, `/var/lib/magnolia/history` | Cache, uploads, and publishing history |
| `/var/lib/magnolia/keys` | Generated application keys |
| `/var/log/magnolia` | Magnolia logs |
| `/opt/magnolia/logs`, `/opt/magnolia/work`, `/opt/magnolia/temp` | Tomcat logs and working files |

The selected archive uses `jackrabbit-bundle-h2-search.xml`, H2 2.4.240, and Jackrabbit 2.22.8-magnolia. There is no external database or separate mount. Services reuse these directories on reboot. The bootstrap preserves an existing matching installation and data if rerun; a checksum marker rejects an unexpected installed bundle. A new instance downloads the package again and initializes a fresh repository and administrator account. Terraform sets root-volume deletion on termination and leaves EBS encryption at AWS/AMI defaults. P04 verified reboot reuse; P07 owns the full content-retention and instance-replacement demonstration.

## Provisioning integration

`infra/compute.tf` renders the two configuration templates without inputs, then passes their Base64-encoded text to the bootstrap:

```hcl
locals {
  magnolia_user_data = templatefile("${path.module}/templates/bootstrap.sh.tftpl", {
    magnolia_service_b64 = base64encode(templatefile("${path.module}/templates/magnolia.service.tftpl", {}))
    nginx_config_b64     = base64encode(templatefile("${path.module}/templates/nginx.conf.tftpl", {}))
  })
}
```

The instance uses `local.magnolia_user_data` as `user_data` and sets `user_data_replace_on_change = true`. The templates pin the package, ports, context, and paths together; changing those requires a reviewed template update. There are no credential inputs. See the [plan's interface contract](docs/plan.md#p02p03-interface) for network and health-check settings.

Nginx listens on HTTP port 80 and proxies `/magnoliaAuthor/` unchanged to Tomcat on `127.0.0.1:8080`. `/` redirects to the author context. The ALB targets port 80 and checks `/magnoliaAuthor/.rest/health/ready` with success code `200` only. Magnolia's [readiness API](https://docs.magnolia-cms.com/product-docs/6.3/developing/api/health-check-api/) reports failed initialization with HTTP 503. Nginx forwards that response and never substitutes a static success page. Tomcat trusts forwarded protocol headers only from the local Nginx proxy, using its [Remote IP valve](https://tomcat.apache.org/tomcat-9.0-doc/config/valve.html#Remote_IP_Valve); Terraform restricts instance port 80 ingress to the ALB security group. Nginx reads `CloudFront-Forwarded-Proto` and sends the validated protocol to Tomcat as `X-Forwarded-Proto`. It preserves the viewer `Host`. The ALB's own `X-Forwarded-Proto` reports the HTTP origin connection and is deliberately not used for the viewer protocol. Nginx returns relative root/context redirects with `absolute_redirect off`, so those redirects preserve browser HTTPS too.

The bootstrap configures the services before starting them. On each boot, systemd starts Magnolia after the network, waits for an exact HTTP 200 from its readiness endpoint, then starts Nginx. The readiness helper tries 120 times with five-second pauses and five-second request timeouts. Startup can take up to about 20 minutes before that helper fails; the unit allows 25 minutes. Failed Magnolia processes restart with a delay and a bounded start rate. Nginx can continue returning an unhealthy response while Magnolia recovers. There is no ongoing background readiness poll beyond ALB health checks.

## Local provisioning checks

Run from the repository root; this renders files into ignored `build/p02/` and does not run the installer:

```sh
python3 scripts/check-provisioning.py
```

To repeat the download and archive checks:

```sh
mkdir -p build/p02
curl --fail --location --retry 3 \
  https://nexus.magnolia-cms.com/repository/magnolia.public.releases/info/magnolia/demo/travel-demo-community-webapp/6.3.27/travel-demo-community-webapp-6.3.27-tomcat-bundle.zip \
  --output build/p02/magnolia.zip
python3 scripts/check-provisioning.py --archive build/p02/magnolia.zip
```

The helper uses Terraform's real `templatefile` renderer in an empty temporary directory, checks Bash syntax and embedded Python compilation, and runs ShellCheck when installed. With `--archive`, it verifies the checksum, ZIP integrity, bundled versions, embedded persistence, and repeatable configuration edits against archive files. P02 also passed ShellCheck 0.11.0 and a configuration-only check with Nginx 1.24.0 compiled locally; that check relocated log paths into `/tmp` for macOS. It did not start an HTTP server. Native Ubuntu `nginx -t` runs during bootstrap. P04 also passed native Ubuntu systemd verification, apt installation, JVM startup, unattended initialization, exact readiness, ALB registration, browser rendering of the login form, and private authenticated checks.

## Runtime troubleshooting and limits

Runtime diagnostics use `/var/log/cloud-init-output.log`, `/var/log/magnolia-bootstrap.log`, `journalctl -u magnolia`, `/var/log/magnolia/`, `/opt/magnolia/logs/`, and `/var/log/nginx/magnolia-error.log`. The bootstrap reports its failing line and exit code without dumping commands or credential values. A readiness timeout points to the application logs. After fixing a startup failure, an operator can reset the start limit with `systemctl reset-failed magnolia` and restart Magnolia and Nginx. A guarded Magnolia stop produced HTTP 502 and an unhealthy ALB target; restart reached readiness in 57.64 seconds and the target recovered. Reboot recovered automatically (Tomcat startup 109 seconds), reused the repository/sample identifier and password file, and passed private login again. Cloud-init retained one bootstrap completion marker. Temporary test markers and the recovery timer were removed. The final plan reported no changes; no bootstrap or infrastructure fixes were needed.

Magnolia logged an invalid-key-length fallback during first-run key generation; its exact-version source confirms it uses the bundled default afterward. Initialization, all readiness checks, and private login passed. Standard CPU credits can make startup slow; allow the configured readiness window before diagnosing a failure. An HTTP 401 on an author page is its login form, not a failed health check. Stopping Tomcat makes Nginx return 502; ALB health changes only after its configured thresholds, and a sole unhealthy target can still receive requests.

This is a single author demo with embedded persistence and one root disk. It has no content backup, application high availability, or independent public publishing target. Java and Nginx package patch versions depend on the repositories at installation time; only Magnolia and bundled Tomcat are pinned here. The archive checksum was calculated from the official HTTPS download, rather than verified against a separate vendor signature. P04 confirmed initial login and initialized sample content. P07 must demonstrate retention of newly created content after reboot and fresh initialization after instance replacement.

One instance means maintenance, replacement, or a failure interrupts the application. The ALB spans two zones, but the second private subnet has no standby instance. One NAT Gateway in zone `a` serves both private subnets; a NAT or zone outage removes their internet and Systems Manager access, and traffic from zone `b` crosses zones. There is no NAT failover. EC2, EBS, NAT processing, ALB, and public IPv4 addresses incur charges after deployment. The stack remains running and billable. CloudFront adds request and transfer charges. S3 charges for state versions, recovery copies, and requests; versions are retained until an operator removes them. See the teardown order below. Termination deletes the CMS data with the root disk.


## Remote state and bootstrap

The source repository is [amanya/Crescendo-DevOps-exam](https://github.com/amanya/Crescendo-DevOps-exam). It was made private at the user's request after P06 verification. GitHub reports `amanya` as a personal account; access to source, PRs, and Actions logs now requires repository permission.

| Item | Value |
| --- | --- |
| State bucket | `crescendo-exam-tfstate-317399646022-eu-central-1` |
| Workload key | `workload/terraform.tfstate` |
| Native lock key | `workload/terraform.tfstate.tflock` |
| Bootstrap recovery key | `bootstrap/terraform.tfstate` |
| Region / account | `eu-central-1` / `317399646022` |
| CI role | `arn:aws:iam::317399646022:role/crescendo-exam-github-plan` |
| OIDC provider | `arn:aws:iam::317399646022:oidc-provider/token.actions.githubusercontent.com` |

`bootstrap/` is an independent Terraform root with local state. It creates the bucket, versioning, bucket-owner-enforced ownership, all four public-access blocks, a TLS-only bucket policy, and the OIDC provider/role/policy. Inspection found no GitHub OIDC provider in this account, so this configuration created it. In an account with an existing provider, inspect its audience configuration and import it into the bootstrap before applying; do not create a duplicate or remove a shared provider during teardown.

The bucket uses AWS's normal SSE-S3 encryption defaults, verified as `AES256`. There is no custom key, encryption override, DynamoDB table, or content backup. `prevent_destroy` and `force_destroy = false` protect against accidental bucket deletion. Versioning retains old state and lock versions, including delete markers; it does not prevent a privileged operator from deleting versions. Access logging, CloudTrail S3 data events, and CloudWatch request monitoring are recommended for a longer-lived environment but are outside this exam's agreed scope and would add configuration and charges.

To bootstrap a new environment after reviewing names, account, repository IDs, and trust:

```sh
umask 077
mkdir -p build/p06/backups
chmod 700 build/p06 build/p06/backups
AWS_PROFILE=default terraform -chdir=bootstrap init -input=false -lockfile=readonly
terraform -chdir=bootstrap fmt -check
terraform -chdir=bootstrap validate
AWS_PROFILE=default terraform -chdir=bootstrap plan -out=../build/p06/bootstrap.tfplan
AWS_PROFILE=default terraform -chdir=bootstrap apply ../build/p06/bootstrap.tfplan
chmod 600 bootstrap/terraform.tfstate
```

Preserve `bootstrap/terraform.tfstate` after every bootstrap apply in restricted local storage and at `s3://crescendo-exam-tfstate-317399646022-eu-central-1/bootstrap/terraform.tfstate`. P06 uploaded a recovery snapshot through an AWS MCP presigned upload and verified it by downloading to restricted storage and comparing it byte for byte. An authenticated operator can also use `AWS_PROFILE=default aws s3 cp bootstrap/terraform.tfstate s3://crescendo-exam-tfstate-317399646022-eu-central-1/bootstrap/terraform.tfstate --region eu-central-1 --only-show-errors`. The recovery copy is versioned and unavailable to CI. Keep a separate restricted copy outside the checkout before deleting the checkout or bucket. The bootstrap's local backend avoids making the bucket depend on a backend it must create; serialize bootstrap changes manually.

### Workload migration and identity checks

P06 first copied the existing local workload state to ignored `build/p06/backups/workload-before.tfstate` with directory mode `0700` and file mode `0600`. It then added `infra/backend.tf` and used Terraform's [supported migration process](https://developer.hashicorp.com/terraform/cli/commands/init):

```sh
umask 077
cp infra/terraform.tfstate build/p06/backups/workload-before.tfstate
chmod 600 build/p06/backups/workload-before.tfstate
AWS_PROFILE=default terraform -chdir=infra init -migrate-state -force-copy -input=false -lockfile=readonly
AWS_PROFILE=default terraform -chdir=infra state pull > build/p06/workload-after.tfstate
AWS_PROFILE=default terraform -chdir=infra plan -input=false -detailed-exitcode -out=../build/p06/verified-migration.tfplan
```

The migration copied every resource identity but assigned a new lineage and serial. Verification caught this before completion. With no concurrent writers, the agent preserved the migrated snapshot, compared every state field except snapshot metadata against the original backup, and used the documented [state recovery command](https://developer.hashicorp.com/terraform/cli/commands/state/push) to restore the original snapshot. The explicit `-force` was limited to that checked recovery; do not use it as a routine migration command. The final state retains the original lineage and all 33 managed resource IDs, including EC2 `i-03e2b17589905593d` and CloudFront `E178D8X4DHIIP9`. Its serial advanced from 41 to 42 during recovery. The fresh remote-state plan exited 0 with no changes. No workload apply, replacement, reboot, or CMS reset occurred.

For any future migration, compare lineage and all managed resource addresses/indexes/IDs before considering it complete. `init -reconfigure` alone does not migrate state. Keep the old snapshot until the remote-state identity checks and a fresh plan pass. Ignore rules exclude state, backups, `.terraform/` backend caches, native lock files, saved plans, logs, variable files, and generated output. Keep `umask 077` for state/plan operations and never publish their contents.

### Local and CI authentication

Neither AWS provider configuration nor the S3 backend hardcodes a profile. Locally, use `AWS_PROFILE=default`; CI receives temporary environment credentials from GitHub OIDC. Do not set `AWS_PROFILE` in GitHub Actions or upload local AWS configuration. The account guard and region remain fixed. No long-lived AWS access key was added to GitHub.

The repository's initial OIDC settings reported immutable subjects enabled and default prefix `repo:amanya@4490611/Crescendo-DevOps-exam@1420637563`. Following [GitHub's OIDC subject documentation](https://docs.github.com/en/actions/reference/security/oidc), P06 configured `use_default=false` with `include_claim_keys=["repository_id", "repository_owner_id", "context", "job_workflow_ref"]`. The intended subject is:

```text
repository_id:1420637563:repository_owner_id:4490611:pull_request:job_workflow_ref:amanya/Crescendo-DevOps-exam/.github/workflows/terraform-plan.yml@refs/heads/main
```

The actual PR workflow confirmed this exact subject and the `sts.amazonaws.com` audience. It prints only the subject, audience, and reusable-workflow reference, never the token. IAM requires an exact subject match and audience `sts.amazonaws.com`. The identity provider URL is `https://token.actions.githubusercontent.com`. Changing repository ownership, OIDC customization, or the trusted workflow reference requires a deliberate trust-policy review. GitHub's [reusable workflow OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows) explains the workflow binding.

Set these nonsecret repository variables under Settings -> Secrets and variables -> Actions -> Variables. They were configured for P06:

| Variable | Purpose |
| --- | --- |
| `AWS_PLAN_ROLE_ARN` | Planning role ARN above |
| `TF_STATE_LINEAGE` | Original workload lineage; compare with a restricted state pull |
| `TF_STATE_IDENTITIES_SHA256` | SHA-256 of the canonical managed-resource identity list below |

The canonical list contains `[module-or-empty-string, resource-type, resource-name, index-key-or-null, id]` for each managed instance in raw state. Sort rows by Python `json.dumps(row)` and hash UTF-8 `json.dumps(rows, separators=(',', ':'))`. The workflow implements this algorithm before planning and fails if lineage or identities differ. After an authorized manual deployment changes resource identities, verify the new state locally and update the identity variable before expecting subsequent PR plans to pass. If a deployment replaces CloudFront resources, review the bootstrap policy's specific read ARNs too. Never copy whole state into a repository variable.

### PR checks and trust boundaries

`.github/workflows/terraform.yml` runs on `pull_request` to `main`. Every PR runs `terraform fmt -check -recursive` and initializes/validates both Terraform roots with `-backend=false`, fresh temporary data directories, and no AWS credentials. Actions are pinned to commit SHAs; Terraform is pinned to 1.16.6 and provider selections use committed lock files.

A same-repository PR, targeting `main` and initiated by a non-Dependabot actor, can call `.github/workflows/terraform-plan.yml@main`. That reusable workflow repeats the trust gate before obtaining an OIDC token or checking out code. IAM binds the token to this workflow on `main`, so a modified PR caller cannot bypass the gate with another credential-bearing job. Fork PRs run only formatting/validation. There is no `pull_request_target` workflow. Before the visibility change, `main` required `Format and validate`, `Trusted PR / Remote state plan`, and one approving review, dismissed stale reviews, and blocked force pushes/deletion. After making the repository private, GitHub returned HTTP 403 for branch protection and required an upgrade to GitHub Pro or a public repository. These protections are unavailable on the current plan; review the two check results and obtain review manually before merging. A private repository on a supported paid plan can enforce them again. Repository administrators and users who can change the trusted workflow on `main` remain part of the trust boundary; same-repository PR authors are trusted to run Terraform code with the planning role. Review workflow and provider changes carefully.

The plan role has explicit EC2, ELB, IAM, and CloudFront reads for the existing workload. Regional reads are constrained to `eu-central-1`; IAM role/profile and CloudFront reads target the existing workload identity/distribution/policies; prefix-list entry reads target the exact AWS-managed CloudFront list. Some describe/list APIs require `Resource = "*"`. S3 grants `ListBucket` for Terraform's workload/workspace discovery prefixes, `GetObject` only for the workload state, and `GetObject`/`PutObject`/`DeleteObject` only for the exact `.tflock` key, following [HashiCorp's S3 backend permissions](https://developer.hashicorp.com/terraform/language/backend/s3). The role cannot write/delete workload state, read bootstrap state, deploy resources, pass roles, or use Systems Manager. Deployment is a reviewed manual operator action.

Planning is serialized in GitHub and uses S3 native locking with a five-minute wait. Terraform exit 0 means no changes; exit 2 means a successful plan with changes; every other exit fails the job. The job checks migrated-state identity first and exposes only action counts and success/failure. State, saved plans, JSON plans, and full diagnostics remain in a restricted temporary runner directory removed on exit. No plan artifact, full plan comment, or full plan log is published. On a plan failure, only missing API action names may appear publicly; investigate other failures in an authorized private session.

P06's validation PR is [PR #1](https://github.com/amanya/Crescendo-DevOps-exam/pull/1). [The successful source-validation run](https://github.com/amanya/Crescendo-DevOps-exam/actions/runs/38732314501) passed both required checks at commit `873a15f`. It confirmed the exact OIDC subject/audience, the original lineage and all 33 managed resource IDs, and a real plan exit 0 with 33 no-op actions. No workload recreation was proposed. The final documentation commit runs the same checks again; its current status is visible on the PR. P06 is Verified and P07 is Ready. Leave the PR open for review. Collaborator invitations and final submission remain P07 work.

### Recovery and teardown order

For workload-state recovery, stop CI/manual writers first and preserve the current S3 version and a restricted local state pull. Retrieve the chosen prior version into a mode-`0600` file without printing it, then compare lineage, serial, identities, and the live resources. Use Terraform's state recovery commands only after reviewing those differences; do not blindly overwrite a newer state. Recovering state does not restore CMS content. A stale lock can be removed with `terraform -chdir=infra force-unlock LOCK_ID` only after confirming its writer has stopped; never disable locking to work around an active writer.

For bootstrap recovery, retrieve `bootstrap/terraform.tfstate` from its versioned S3 key into the `bootstrap/` directory under `umask 077`, or restore the independent restricted backup. Run bootstrap `init`, `validate`, and `plan` with the local default profile. Verify the eight existing resources are recognized and the plan is empty before another apply. If both state copies are lost, import each existing bucket configuration, OIDC provider, role, and inline policy using provider-documented import IDs; do not apply a creation plan over existing resources. Keep the bucket name, account, region, and bootstrap source available outside the state archive.

When teardown is separately authorized:

1. Disable PR planning and stop all Terraform writers. Preserve both state snapshots and any needed CMS content outside the resources being removed.
2. With the local default profile, review `terraform -chdir=infra plan -destroy`, then destroy the workload while the S3 backend and locking remain available. EC2 termination deletes CMS data with its root disk.
3. Preserve the final workload state and bootstrap state outside the bucket. Remove the CI role/policy; remove the OIDC provider only if it is still unused by other roles.
4. Review a bootstrap teardown that deliberately removes bucket `prevent_destroy`. Remove all object versions and delete markers only after retaining the recovery copies. The bucket's `force_destroy = false` will otherwise block deletion of a nonempty bucket. Destroy the remaining bootstrap resources last.

[Private-repository validation](https://github.com/amanya/Crescendo-DevOps-exam/actions/runs/38733705991) passed both CI jobs, confirmed the original state lineage/all 33 managed IDs, and produced plan exit 0 with 33 no-op actions. Anonymous CloudFront health checks also passed after the visibility change. Private-repository Actions runs consume the account's included minutes or applicable billing allowance; see [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions). The visibility change keeps the configured repository/owner IDs, workflow reference, and OIDC subject; the trust policy does not depend on repository visibility. The deployed application and S3 backend do not fetch source from GitHub and continue running independently. Submission visibility must be confirmed during P07; do not make the repository public again without authorization.

No teardown or collaborator invitation was performed during P06.
