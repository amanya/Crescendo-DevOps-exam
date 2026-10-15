output "vpc_id" {
  description = "VPC used by the exam workload."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public ALB subnets by zone suffix."
  value       = { for key, subnet in aws_subnet.public : key => subnet.id }
}

output "private_subnet_ids" {
  description = "Private subnets by zone suffix; the instance uses a."
  value       = { for key, subnet in aws_subnet.private : key => subnet.id }
}

output "nat_public_ip" {
  description = "Elastic IP used for outbound downloads and Systems Manager."
  value       = aws_eip.nat.public_ip
}

output "instance_id" {
  description = "Private Magnolia instance for Systems Manager and lifecycle checks."
  value       = aws_instance.magnolia.id
}

output "instance_private_ip" {
  description = "Private Nginx target address."
  value       = aws_instance.magnolia.private_ip
}

output "ubuntu_ami_id" {
  description = "Canonical Ubuntu AMI resolved from the reviewed release name."
  value       = data.aws_ami.ubuntu.id
}

output "alb_dns_name" {
  description = "ALB origin hostname; ingress is restricted to CloudFront addresses."
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB hosted zone ID for a later DNS alias if needed."
  value       = aws_lb.main.zone_id
}

output "target_group_arn" {
  description = "Target group to inspect for application readiness."
  value       = aws_lb_target_group.magnolia.arn
}

output "author_url" {
  description = "Public HTTPS author URL through CloudFront."
  value       = "https://${aws_cloudfront_distribution.magnolia.domain_name}/magnoliaAuthor/"
}

output "readiness_url" {
  description = "Readiness URL; only HTTP 200 means Magnolia is ready."
  value       = "https://${aws_cloudfront_distribution.magnolia.domain_name}/magnoliaAuthor/.rest/health/ready"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution for deployment status checks."
  value       = aws_cloudfront_distribution.magnolia.id
}

output "cloudfront_url" {
  description = "Public HTTPS entry point using the default CloudFront certificate."
  value       = "https://${aws_cloudfront_distribution.magnolia.domain_name}"
}
