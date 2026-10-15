data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# Forward Host, Authorization, Origin/Referer, CSRF headers, cookies, and queries.
# ALB replaces X-Forwarded-Proto with its own HTTP connection protocol; carry
# the viewer protocol separately so Nginx can restore it for Tomcat.
resource "aws_cloudfront_origin_request_policy" "magnolia" {
  name    = "${local.name}-magnolia"
  comment = "All viewer request data and the CloudFront viewer protocol"

  cookies_config {
    cookie_behavior = "all"
  }
  query_strings_config {
    query_string_behavior = "all"
  }
  headers_config {
    header_behavior = "allViewerAndWhitelistCloudFront"
    headers {
      items = ["CloudFront-Forwarded-Proto"]
    }
  }
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_distribution" "magnolia" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Magnolia development author application"
  price_class         = "PriceClass_100"
  wait_for_deployment = true

  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "magnolia-alb"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      origin_read_timeout    = 120
    }
  }

  default_cache_behavior {
    target_origin_id           = "magnolia-alb"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = aws_cloudfront_origin_request_policy.magnolia.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
    compress                   = true
  }

  # Error caching is separate from the cache policy. Preserve each status/body
  # and fetch failures afresh, including readiness while the application starts.
  dynamic "custom_error_response" {
    for_each = toset([400, 403, 404, 405, 414, 416, 500, 501, 502, 503, 504])
    content {
      error_code            = custom_error_response.value
      error_caching_min_ttl = 0
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  depends_on = [aws_lb_listener.http]
}
