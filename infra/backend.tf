terraform {
  backend "s3" {
    bucket              = "crescendo-exam-tfstate-317399646022-eu-central-1"
    key                 = "workload/terraform.tfstate"
    region              = "eu-central-1"
    allowed_account_ids = ["317399646022"]
    use_lockfile        = true
  }
}
