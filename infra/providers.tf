provider "aws" {
  profile = "default"
  region  = "eu-central-1"

  allowed_account_ids = ["317399646022"]

  default_tags {
    tags = {
      Project   = "crescendo-devops-exam"
      ManagedBy = "Terraform"
    }
  }
}
