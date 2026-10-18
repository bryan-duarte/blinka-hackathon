# Edge (ALB + HTTPS) Implementation

## Overview

This module puts the internet-facing ALB in the public subnets, at `https://api.<domain>`, with an ACM certificate validated through Route53. It is the only resource in the VPC that the internet can reach.

## Files to Modify/Create

- `infra/edge.tf` (new) defines:
  - `data "aws_route53_zone" "main"`
  - `aws_acm_certificate.api`, `aws_route53_record.api_cert_validation` (for_each), `aws_acm_certificate_validation.api`
  - `aws_lb.api`, `aws_lb_target_group.api`
  - `aws_lb_listener.https`, `aws_lb_listener.http_redirect`
  - `aws_route53_record.api`
- `infra/variables.tf` adds `domain_name` (string, required) and `api_subdomain` (string, default `"api"`).

## Implementation Guidelines

```hcl
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

resource "aws_acm_certificate" "api" {
  domain_name       = local.api_host
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for o in aws_acm_certificate.api.domain_validation_options : o.domain_name => o
  }
  zone_id = data.aws_route53_zone.main.zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for r in aws_route53_record.api_cert_validation : r.fqdn]
}

resource "aws_lb" "api" {
  name               = "blinka-api"
  load_balancer_type = "application"
  internal           = false
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = 120 # uploads wait up to ~60s on the GuardDuty scan
}

resource "aws_lb_target_group" "api" {
  name                 = "blinka-api"
  vpc_id               = aws_vpc.main.id
  target_type          = "ip"
  protocol             = "HTTP"
  port                 = 8000
  deregistration_delay = 30
  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}
```

The listeners:
- `aws_lb_listener.https` listens on port 443 with protocol HTTPS.
  - Set `ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"`.
  - Set `certificate_arn = aws_acm_certificate_validation.api.certificate_arn`, which forces Terraform to wait for validation.
  - The default action forwards to `aws_lb_target_group.api`.
- `aws_lb_listener.http_redirect` listens on port 80. Its default action is `redirect { port = "443", protocol = "HTTPS", status_code = "HTTP_301" }`.

`aws_route53_record.api` creates `name = local.api_host`, `type = "A"`, `alias { name = aws_lb.api.dns_name, zone_id = aws_lb.api.zone_id, evaluate_target_health = true }`.

## Dependencies

- From module 02: `aws_subnet.public`, `aws_security_group.alb`, `aws_vpc.main` and `local.api_host`.
- A public Route53 hosted zone for `var.domain_name` must already exist in the account.

## Integration Notes

- Module 06 attaches the ECS service with `load_balancer { target_group_arn = aws_lb_target_group.api.arn, container_name = "backend", container_port = 8000 }`. It also adds `depends_on = [aws_lb_listener.https]`.
- `local.api_host` is used in module 05 for `BLINKA_KAPSO__WEBHOOK_URL` and in the `api_url` output.
