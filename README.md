# Crescendo DevOps exam

Deploy Magnolia Community Edition on AWS with Terraform for the Crescendo DevOps exam. The planned request path is browser -> CloudFront -> ALB -> Nginx -> Tomcat/Magnolia on one private EC2 instance.

## Current status

P01, P02, and P03 are verified for preparation. P04 is verified: Terraform applied all 31 planned resources in account `317399646022`, region `eu-central-1`, on 2026-10-15. Magnolia initialized automatically and is reachable through the public ALB. Private login, sample content, assets, sessions, Magnolia stop/start recovery, and reboot reuse passed. The final Terraform plan reports no changes. P05 is Ready. CloudFront belongs to P05; remote state and CI belong to P06.

The infrastructure uses two public and two private subnets across two availability zones, one NAT Gateway, and one private EC2 instance. The OS, software, and CMS data share one EBS root volume, deleted on termination. Instance replacement reinstalls the application and starts a fresh CMS. EBS encryption follows the AWS account and AMI defaults.

See [the plan](docs/plan.md) for scope, acceptance criteria, validation evidence, and the complete P02/P03 interface.

## Prerequisites

- Git. Local setup was checked with Git 2.50.1.
- Terraform 1.16.6 or a newer 1.16 patch release. The configuration restricts Terraform to `~> 1.16.6`.
- AWS CLI v2 for later AWS access and deployment work. Version 2.35.13 is installed locally. The intended AWS profile is `default`, and the workload region is `eu-central-1`.
- Network access to the [Terraform Registry](https://registry.terraform.io/providers/hashicorp/aws) and HashiCorp's provider downloads during initialization.
- Python 3 for the local provisioning checker. ShellCheck is optional; the checker runs it when available.

GitHub CLI 2.95.0 is also installed locally; it is optional for P01. AWS credentials are not needed for `terraform init`, `terraform fmt`, or `terraform validate`. Planning and deployment require a working `default` profile and suitable AWS permissions. Keep credential material outside the repository in your normal AWS configuration.

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
terraform -chdir=infra init -input=false
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
```

Initialization downloads the provider and uses Terraform's default local backend. It does not create AWS resources. Remote state belongs to P06. Commit the provider lock file whenever an intentional dependency update changes it; follow the [HashiCorp lock-file guidance](https://developer.hashicorp.com/terraform/language/files/dependency-lock).

The `.gitignore` excludes local state, plans, provider downloads, variable files, environment files, credentials, and generated application artifacts. It keeps `.terraform.lock.hcl` tracked. Review files before committing them; ignore patterns cannot detect every sensitive value.

## Repository layout

```text
AGENTS.md                   Project instructions
README.md                   Purpose, prerequisites, and local setup
docs/plan.md                Scope, task status, and validation evidence
infra/versions.tf           Terraform and AWS provider constraints
infra/providers.tf          AWS profile, region, account guard, and default tags
infra/variables.tf          Reviewed Ubuntu AMI release input
infra/network.tf            VPC, subnets, Internet Gateway, NAT, and routing
infra/compute.tf            AMI, instance role/profile, security group, and EC2
infra/load-balancer.tf      ALB security group, listener, target, and health check
infra/outputs.tf            Verification endpoints, resource IDs, and origin hostname
infra/.terraform.lock.hcl   Provider selection and checksums
infra/templates/           Bootstrap, Nginx site, and Magnolia systemd unit
scripts/check-provisioning.py  Local template and archive checks
scripts/check-runtime.py       Sanitized on-instance diagnostics
scripts/check-private-login.py  SSM/loopback login, content, and session checks
```

## Infrastructure and sizing

Terraform uses profile `default` in `eu-central-1` and refuses accounts other than `317399646022`. Resources carry `Project=crescendo-devops-exam` and `ManagedBy=Terraform` tags where supported. The configuration uses a local backend until P06.

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

The ALB security group accepts public TCP 80 and sends TCP 80 only to the instance security group. The instance accepts TCP 80 only from the ALB security group and permits outbound TCP 80/443 for Ubuntu packages, Magnolia, and Systems Manager through NAT. The VPC resolver provides DNS. There is no inbound rule for SSH or Tomcat; the existing template binds Tomcat to `127.0.0.1:8080`. HTTP is unencrypted at this stage, and the ALB is directly reachable. Browser HTTPS and the CloudFront origin connection policy remain P05 decisions.

The instance profile trusts EC2 and attaches only `AmazonSSMManagedInstanceCore`. Ubuntu Server 24.04 images [include SSM Agent](https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html); P04 confirmed agent `3.3.4793.0` running and the node Online. Its HTTPS connections use NAT, so this configuration needs no VPC endpoints or inbound management ports. Human operators separately need Systems Manager session permissions and either the AWS console or the CLI Session Manager plugin. Session output logging is not configured here.

EC2 explicitly depends on both default routes, all public/private route-table associations, its security-group rules, and the SSM policy attachment. The NAT Gateway also waits for public routing. This makes Terraform establish the outbound path before cloud-init downloads packages or Magnolia. It does not prove the remote repositories or application are available at runtime.

## Plan review and deployment prerequisites

The checked configuration requires no variable file. Planning needs STS identity access and EC2 image lookup permissions. The deployer must also be able to create, read, tag, update, and delete the planned EC2/VPC, Elastic IP/NAT, ELBv2, and IAM resources, attach the SSM managed policy, and pass the instance role to EC2. Elastic Load Balancing may need permission to create its service-linked role if it is absent. A successful plan does not verify these write permissions or available quotas/capacity.

Before a new deployment, confirm capacity and quotas for a VPC, four subnets, one NAT Gateway/Elastic IP, an ALB/target group, and a 2-vCPU on-demand instance. Keep the chosen AMI available, the Ubuntu repositories and `nexus.magnolia-cms.com` reachable, and public TCP 80 reachable for the ALB integration check. No certificate, domain, application secret input, remote backend, or GitHub setup is required for this stage.

To prepare a fresh plan, run from the repository root:

```sh
mkdir -p build/p04
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
python3 scripts/check-provisioning.py
terraform -chdir=infra plan -input=false -out=../build/p04/deploy.tfplan
terraform -chdir=infra show ../build/p04/deploy.tfplan
```

P04 generated and inspected a fresh plan against the current account and local state, then applied the saved plan with 31 creations and no updates/deletions. It checked quotas and IAM permissions first. Before any later apply, review the root-volume lifecycle, routing and dependencies, security-group references, health settings, and rendered user data. The bootstrap matches the committed P02/P03 configuration byte for byte at 9,442 bytes, below EC2's 16 KiB limit. Generated plans, logs, rendered files, and state remain ignored; do not commit them.

After reviewing the saved plan, apply that exact file:

```sh
terraform -chdir=infra apply ../build/p04/deploy.tfplan
terraform -chdir=infra output
```

Preserve `infra/terraform.tfstate` and its backup locally until P06 migrates them. Losing state does not remove the running resources. P05 can use `alb_dns_name` as its CloudFront origin. Terraform finishing an apply does not confirm cloud-init or application readiness.

## Running development stack

| Item | Deployed value |
| --- | --- |
| Author | [Magnolia login](http://crescendo-exam-1001328653.eu-central-1.elb.amazonaws.com/magnoliaAuthor/) |
| Readiness | [Magnolia readiness](http://crescendo-exam-1001328653.eu-central-1.elb.amazonaws.com/magnoliaAuthor/.rest/health/ready), exact HTTP 200 when ready |
| Instance | `i-07fcc5e12ec293cdb`, private `10.42.10.96` |
| Root volume | `vol-0ff200cdf4391daa8`, 30 GiB gp3, deleted on termination; unencrypted under the current account/AMI defaults |
| VPC | `vpc-0dae6a3137091be57` |
| NAT Gateway | `nat-083d0e0c9070b58d4`, EIP `18.195.185.6` |
| ALB | `arn:aws:elasticloadbalancing:eu-central-1:317399646022:loadbalancer/app/crescendo-exam/5836054be05d28c9` |
| Target group | `arn:aws:elasticloadbalancing:eu-central-1:317399646022:targetgroup/crescendo-exam-magnolia/b2a5f934ec75e3ed` |
| Security groups | ALB `sg-0d2eb879407ba8780`; instance `sg-0b53b8f372914cf56` |

The public author page returns HTTP 401 with Magnolia's login form until authenticated. `/` and `/magnoliaAuthor` redirect to `/magnoliaAuthor/`; the login CSS and images return 200 through the ALB. Readiness is unauthenticated and returns 200 only after the `magnolia-instance`, `datastore`, and `admin-setup` checks are UP. Do not enter credentials at the public HTTP URL. Browser HTTPS and authenticated behavior through CloudFront remain P05 checks.

P04 used AWS MCP Systems Manager Run Command to run `scripts/check-runtime.py` on the instance as root. It prints service/package/health results and resource measurements, and summarizes log markers without returning arbitrary log lines. The private login helper, `scripts/check-private-login.py`, runs only against loopback Nginx. It reads the local password into memory, submits the CSRF-protected form, checks session rotation and authenticated content, then logs out. Run it only in an authorized private SSM context; never paste credentials, cookies, response HTML, or unsanitized logs into evidence. The user authorized this local-file workflow as a P04 exception to the Secrets Manager/`asm-exec` rule after the required secret skill was loaded. No Secrets Manager resource or additional IAM access was added.

Private checks passed for administrator login, AdminCentral, the initialized Travel page and REST node, six referenced content assets, and 95 installed modules. Login rotated the session; subsequent requests reused it, and logout restored HTTP 401. The session cookie was HttpOnly with path `/magnoliaAuthor`; Secure was false over local HTTP. Credentials and session cookies were never sent over the public HTTP connection. After reboot, private checks confirmed the same repository/sample identifier and password file, then repeated login, content, assets, sessions, and logout successfully. P07 owns the full content-retention and replacement demonstration.

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

Nginx listens on HTTP port 80 and proxies `/magnoliaAuthor/` unchanged to Tomcat on `127.0.0.1:8080`. `/` redirects to the author context. The ALB targets port 80 and checks `/magnoliaAuthor/.rest/health/ready` with success code `200` only. Magnolia's [readiness API](https://docs.magnolia-cms.com/product-docs/6.3/developing/api/health-check-api/) reports failed initialization with HTTP 503. Nginx forwards that response and never substitutes a static success page. Tomcat trusts forwarded protocol headers only from the local Nginx proxy, using its [Remote IP valve](https://tomcat.apache.org/tomcat-9.0-doc/config/valve.html#Remote_IP_Valve); Terraform restricts instance port 80 ingress to the ALB security group. P05 still needs to verify browser HTTPS, forwarded protocol, redirects, and sessions after choosing the origin connection policy.

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

One instance means maintenance, replacement, or a failure interrupts the application. The ALB spans two zones, but the second private subnet has no standby instance. One NAT Gateway in zone `a` serves both private subnets; a NAT or zone outage removes their internet and Systems Manager access, and traffic from zone `b` crosses zones. There is no NAT failover. EC2, EBS, NAT processing, ALB, and public IPv4 addresses incur charges after deployment. The stack remains running and billable for P05. CloudFront, remote state, CI, and publication remain later tasks. When teardown is authorized, review `terraform -chdir=infra plan -destroy` and run `terraform -chdir=infra destroy` against the preserved state. Termination deletes the CMS data with the root disk.
