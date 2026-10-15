# Crescendo DevOps exam

Deploy Magnolia Community Edition on AWS with Terraform for the Crescendo DevOps exam. The planned request path is browser -> CloudFront -> ALB -> Nginx -> Tomcat/Magnolia on one private EC2 instance.

## Current status

P01 is complete: the local repository and Terraform tooling are initialized and verified. The Terraform configuration currently contains version constraints and the AWS provider only. No AWS resources are defined or deployed by this repository, and there is no remote state or CI workflow yet.

The agreed architecture uses two public and two private subnets across two availability zones, one NAT Gateway, and one private EC2 instance. The OS, software, and CMS data will share one EBS root volume, deleted on termination. Instance replacement will reinstall the application and start a fresh CMS. EBS encryption will follow the AWS account and AMI defaults.

See [the plan](docs/plan.md) for scope, acceptance criteria, decisions, and progress. P02 will determine the Magnolia artifact and compatible Java/Tomcat versions before application provisioning is implemented.

## Prerequisites

- Git. Local setup was checked with Git 2.50.1.
- Terraform 1.16.6 or a newer 1.16 patch release. The configuration restricts Terraform to `~> 1.16.6`.
- AWS CLI v2 for later AWS access and deployment work. Version 2.35.13 is installed locally. The intended AWS profile is `default`, and the workload region is `eu-central-1`.
- Network access to the [Terraform Registry](https://registry.terraform.io/providers/hashicorp/aws) and HashiCorp's provider downloads during initialization.

GitHub CLI 2.95.0 is also installed locally; it is optional for P01. AWS credentials are not needed for `terraform init`, `terraform fmt`, or `terraform validate`. Later planning and deployment require a working `default` profile and suitable AWS permissions. Keep credential material outside the repository in your normal AWS configuration.

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
infra/providers.tf          AWS profile and region
infra/.terraform.lock.hcl   Provider selection and checksums
```

Additional directories will be created when their first useful files are added.
