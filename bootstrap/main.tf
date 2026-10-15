terraform {
  required_version = "~> 1.16.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.69.0"
    }
  }
  # Deliberately local. Preserve a restricted copy in the bucket after each apply.
}

provider "aws" {
  region              = "eu-central-1"
  allowed_account_ids = ["317399646022"]
  default_tags {
    tags = {
      Project   = "crescendo-devops-exam"
      ManagedBy = "Terraform"
    }
  }
}

locals {
  bucket    = "crescendo-exam-tfstate-317399646022-eu-central-1"
  state_key = "workload/terraform.tfstate"
  # GitHub custom subject: repository_id, repository_owner_id, context, job_workflow_ref.
  pr_subject = "repository_id:1420637563:repository_owner_id:4490611:pull_request:job_workflow_ref:amanya/Crescendo-DevOps-exam/.github/workflows/terraform-plan.yml@refs/heads/main"
}

resource "aws_s3_bucket" "state" {
  bucket        = local.bucket
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

# No encryption override: new S3 objects use AWS's default SSE-S3 encryption.
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireTLS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

# Inspection found no existing GitHub provider in this account. If one already
# exists in a new account, import it here and review before applying.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

resource "aws_iam_role" "plan" {
  name                 = "crescendo-exam-github-plan"
  description          = "Read-only workload plans from the trusted GitHub PR workflow"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = local.pr_subject
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "plan" {
  name = "workload-plan"
  role = aws_iam_role.plan.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "ListBackend"
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = aws_s3_bucket.state.arn
        Condition = { StringLike = { "s3:prefix" = [local.state_key, "env:/", "env:/*"] } }
      },
      {
        Sid      = "ReadWorkloadState"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.state.arn}/${local.state_key}"
      },
      {
        Sid      = "ManageWorkloadLock"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.state.arn}/${local.state_key}.tflock"
      },
      {
        Sid    = "RefreshEC2"
        Effect = "Allow"
        Action = [
          "ec2:DescribeAddresses", "ec2:DescribeImages", "ec2:DescribeInstances",
          "ec2:DescribeInstanceAttribute", "ec2:DescribeInstanceCreditSpecifications",
          "ec2:DescribeInternetGateways", "ec2:DescribeManagedPrefixLists",
          "ec2:DescribeNatGateways", "ec2:DescribeRouteTables",
          "ec2:DescribeSecurityGroups", "ec2:DescribeSecurityGroupRules",
          "ec2:DescribeSubnets", "ec2:DescribeTags", "ec2:DescribeVolumes",
          "ec2:DescribeVpcs", "ec2:DescribeVpcAttribute"
        ]
        Resource  = "*"
        Condition = { StringEquals = { "aws:RequestedRegion" = "eu-central-1" } }
      },
      {
        Sid    = "RefreshELB"
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeLoadBalancerAttributes",
          "elasticloadbalancing:DescribeListeners", "elasticloadbalancing:DescribeListenerAttributes",
          "elasticloadbalancing:DescribeTargetGroups", "elasticloadbalancing:DescribeTargetGroupAttributes",
          "elasticloadbalancing:DescribeTargetHealth", "elasticloadbalancing:DescribeTags"
        ]
        Resource  = "*"
        Condition = { StringEquals = { "aws:RequestedRegion" = "eu-central-1" } }
      },
      {
        Sid      = "RefreshInstanceIdentity"
        Effect   = "Allow"
        Action   = ["iam:GetRole", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:GetInstanceProfile"]
        Resource = ["arn:aws:iam::317399646022:role/crescendo-exam-ssm", "arn:aws:iam::317399646022:instance-profile/crescendo-exam-ssm"]
      },
      {
        Sid      = "FindManagedCloudFrontPolicies"
        Effect   = "Allow"
        Action   = ["cloudfront:ListCachePolicies", "cloudfront:ListResponseHeadersPolicies"]
        Resource = "*"
      },
      {
        Sid      = "ReadManagedCloudFrontPolicies"
        Effect   = "Allow"
        Action   = ["cloudfront:GetCachePolicy", "cloudfront:GetResponseHeadersPolicy"]
        Resource = ["arn:aws:cloudfront::aws:cache-policy/*", "arn:aws:cloudfront::aws:response-headers-policy/*"]
      },
      {
        Sid      = "RefreshCloudFront"
        Effect   = "Allow"
        Action   = ["cloudfront:GetDistribution", "cloudfront:GetOriginRequestPolicy", "cloudfront:ListTagsForResource"]
        Resource = ["arn:aws:cloudfront::317399646022:distribution/E178D8X4DHIIP9", "arn:aws:cloudfront::317399646022:origin-request-policy/*"]
      }
    ]
  })
}

output "state_bucket" {
  value = aws_s3_bucket.state.id
}

output "plan_role_arn" {
  value = aws_iam_role.plan.arn
}

output "oidc_subject" {
  value = local.pr_subject
}
