variable "ubuntu_ami_name" {
  description = "Reviewed Canonical Ubuntu Server 24.04 amd64 AMI release. Changing it replaces the instance and resets CMS data."
  type        = string
  default     = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20261004"

  validation {
    condition     = can(regex("^ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24\\.04-amd64-server-[0-9]{8}$", var.ubuntu_ami_name))
    error_message = "Use an exact Ubuntu Server 24.04 amd64 release name, without wildcards."
  }
}
