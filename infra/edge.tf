locals {
  alb_idle_timeout_seconds           = 120
  target_deregistration_seconds      = 30
  health_check_interval_seconds      = 15
  cert_validation_record_ttl_seconds = 60
  modern_tls_policy                  = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

# The parent domain's DNS (Cloudflare) delegates this zone with NS records
# pointing at its name_servers; ACM validation hangs until that delegation exists.
resource "aws_route53_zone" "main" {
  name          = var.domain_name
  force_destroy = true
}

resource "aws_acm_certificate" "api" {
  domain_name       = local.api_host
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for option in aws_acm_certificate.api.domain_validation_options : option.domain_name => option
  }

  zone_id = aws_route53_zone.main.zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = local.cert_validation_record_ttl_seconds
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.api_cert_validation : record.fqdn]
}

resource "aws_lb" "api" {
  name               = "${local.name}-api"
  load_balancer_type = "application"
  internal           = false
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = local.alb_idle_timeout_seconds
}

resource "aws_lb_target_group" "api" {
  name                 = "${local.name}-api"
  vpc_id               = aws_vpc.main.id
  target_type          = "ip"
  protocol             = "HTTP"
  port                 = local.backend_container_port
  deregistration_delay = local.target_deregistration_seconds

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = local.health_check_interval_seconds
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = local.modern_tls_policy
  certificate_arn   = aws_acm_certificate_validation.api.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = local.api_host
  type    = "A"

  alias {
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
    evaluate_target_health = true
  }
}
