# Project instructions

## Documentation

- Use the installed humanizer skill when writing or editing project prose. Preserve technical meaning, commands, paths, and code.
- Do not hard-wrap documentation prose to a fixed character count.
- Preserve Markdown structure, commands, URLs, identifiers, and code.

## Plan and progress

- Read `docs/plan.md` before starting project work. It records the agreed scope, task dependencies, acceptance criteria, decisions, and current progress.
- Keep the plan current when task status, scope, dependencies, or decisions change. Record blockers and the next actionable step.
- Mark tasks verified only after checking their acceptance criteria. Record concise validation evidence without exposing secrets or sensitive output.
- Keep changes focused and reviewable. At review checkpoints, summarize the changes, validation, remaining limitations, and next task.
- Keep the README consistent with the implemented and verified system.

## Implementation scope

- Use Terraform for infrastructure, as required by this project's exam.
- Use AWS profile `default` and workload region `eu-central-1`.
- Start with one private EC2 instance and one EBS root volume for the OS, application, and CMS data. Delete the root volume on termination.
- Use the AWS account and AMI defaults for EBS encryption. Do not add an explicit encryption override or custom key management for this exercise.
- Rebuild the application automatically on instance replacement. A fresh CMS repository after replacement is intentional for this environment.
- Follow the agreed scope in `docs/plan.md`; discuss additional architecture before adding it.

## Agent coordination

- When the user requests delegation, assign bounded tasks from `docs/plan.md`.
- Record each agent's task, owned files, dependencies, and acceptance criteria before dispatch. Assign one editor per file at a time.
- Agree on shared interfaces before parallel implementation. The primary agent maintains the plan, integrates changes, and verifies the combined result.

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance
- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.
## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->
