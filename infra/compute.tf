data "aws_ami" "ubuntu" {
  owners = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = [var.ubuntu_ami_name]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  magnolia_user_data = templatefile("${path.module}/templates/bootstrap.sh.tftpl", {
    magnolia_service_b64 = base64encode(templatefile("${path.module}/templates/magnolia.service.tftpl", {}))
    nginx_config_b64     = base64encode(templatefile("${path.module}/templates/nginx.conf.tftpl", {}))
  })
}

resource "aws_iam_role" "instance" {
  name        = "${local.name}-ssm"
  description = "Systems Manager access for the private Magnolia instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "instance" {
  name = "${local.name}-ssm"
  role = aws_iam_role.instance.name
}

resource "aws_security_group" "instance" {
  name        = "${local.name}-instance"
  description = "Magnolia HTTP from the ALB only"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-instance" }
}

resource "aws_vpc_security_group_ingress_rule" "instance_http" {
  security_group_id            = aws_security_group.instance.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
  description                  = "Nginx requests and readiness checks from the ALB"
}

resource "aws_vpc_security_group_egress_rule" "instance_http" {
  security_group_id = aws_security_group.instance.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "Ubuntu package downloads through NAT"
}

resource "aws_vpc_security_group_egress_rule" "instance_https" {
  security_group_id = aws_security_group.instance.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "Magnolia downloads and Systems Manager through NAT"
}

resource "aws_instance" "magnolia" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.medium"
  subnet_id                   = aws_subnet.private["a"].id
  associate_public_ip_address = false
  vpc_security_group_ids      = [aws_security_group.instance.id]
  iam_instance_profile        = aws_iam_instance_profile.instance.name
  user_data                   = local.magnolia_user_data
  user_data_replace_on_change = true

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  credit_specification {
    cpu_credits = "standard"
  }

  tags = { Name = "${local.name}-magnolia" }

  # Subnet references alone do not wait for routes, associations, or SG rules.
  # Cloud-init needs outbound access immediately for apt and the Magnolia ZIP.
  depends_on = [
    aws_route.public_internet,
    aws_route.private_internet,
    aws_route_table_association.public,
    aws_route_table_association.private,
    aws_iam_role_policy_attachment.ssm,
    aws_vpc_security_group_ingress_rule.instance_http,
    aws_vpc_security_group_egress_rule.instance_http,
    aws_vpc_security_group_egress_rule.instance_https,
  ]
}
