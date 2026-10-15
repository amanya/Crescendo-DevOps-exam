resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Public HTTP entry point"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-alb" }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "Public HTTP for the P04 ALB integration check"
}

resource "aws_vpc_security_group_egress_rule" "alb_http" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.instance.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
  description                  = "Requests and readiness checks to Nginx only"
}

resource "aws_lb" "main" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  ip_address_type    = "ipv4"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [for subnet in aws_subnet.public : subnet.id]
  idle_timeout       = 120

  depends_on = [
    aws_route.public_internet,
    aws_route_table_association.public,
    aws_vpc_security_group_ingress_rule.alb_http,
    aws_vpc_security_group_egress_rule.alb_http,
  ]
}

resource "aws_lb_target_group" "magnolia" {
  name        = "${local.name}-magnolia"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"
  protocol    = "HTTP"
  port        = 80

  health_check {
    enabled             = true
    protocol            = "HTTP"
    port                = "traffic-port"
    path                = "/magnoliaAuthor/.rest/health/ready"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  protocol          = "HTTP"
  port              = 80

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.magnolia.arn
  }
}

resource "aws_lb_target_group_attachment" "magnolia" {
  target_group_arn = aws_lb_target_group.magnolia.arn
  target_id        = aws_instance.magnolia.id
  port             = 80
}
