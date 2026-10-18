# Network Implementation

## Overview

A VPC with 3 subnet tiers across 2 AZs, one NAT Gateway, a free S3 gateway endpoint, and security groups chained to each other.

## Files to Modify/Create

- `infra/network.tf` (new): `locals`, `data "aws_availability_zones" "available"`, `aws_vpc.main`, `aws_internet_gateway.main`, `aws_subnet.public|app|db` (each `count = 2`), `aws_eip.nat`, `aws_nat_gateway.main`, `aws_route_table.public|app|db`, `aws_route_table_association.*`, `aws_vpc_endpoint.s3`, `aws_security_group.alb|app|db` + `aws_vpc_security_group_ingress_rule` / `egress_rule`.
- `infra/variables.tf`: add `vpc_cidr` (string, default `"10.20.0.0/16"`).

## Implementation Guidelines

```hcl
locals {
  name       = "blinka"
  env        = "prod"
  ssm_prefix = "/blinka/prod"
  api_host   = "${var.api_subdomain}.${var.domain_name}"
  azs        = slice(data.aws_availability_zones.available.names, 0, 2)
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true # needed for RDS endpoint resolution and ECS Exec
  tags                 = { Name = "${local.name}-${local.env}" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)        # 10.20.0.0/24, 10.20.1.0/24
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-public-${count.index}" }
}
# app: cidrsubnet(var.vpc_cidr, 8, 10 + count.index)
# db:  cidrsubnet(var.vpc_cidr, 8, 20 + count.index)
```

Routing:
- `aws_route_table.public` has `0.0.0.0/0` going to the IGW and is associated with both public subnets.
- `aws_nat_gateway.main` lives in `aws_subnet.public[0]` and uses `aws_eip.nat` (`domain = "vpc"`).
- `aws_route_table.app` has one table with `0.0.0.0/0` going to the NAT and is associated with both app subnets.
- `aws_route_table.db` has no routes besides the implicit local one and is associated with both db subnets. This is what isolates the DB tier.
- `aws_vpc_endpoint.s3` uses `service_name = "com.amazonaws.${var.aws_region}.s3"`, `vpc_endpoint_type = "Gateway"` and `route_table_ids = [aws_route_table.app.id]`. Leave the endpoint policy at its default (full access), since Composio presigned URLs may also go through S3.

Security groups use the standalone rule resources (AWS provider v6 style):
| SG | Ingress | Egress |
|---|---|---|
| `alb` (`blinka-alb`) | tcp 80 and 443 from `0.0.0.0/0` | tcp 8000 to `aws_security_group.app` |
| `app` (`blinka-app`) | tcp 8000 from `aws_security_group.alb` | all to `0.0.0.0/0` (NAT, endpoints, RDS) |
| `db` (`blinka-db`) | tcp 5432 from `aws_security_group.app` | none |

## Dependencies

- `var.aws_region`, which already exists.
- `var.api_subdomain` and `var.domain_name`, both used in `locals` and declared in module 03.

## Integration Notes

The resources and attributes other modules depend on:
- `aws_subnet.public[*].id` is used by the ALB (module 03).
- `aws_subnet.app[*].id` is used by the ECS service (module 06).
- `aws_subnet.db[*].id` is used by the RDS subnet group (module 04).
- `aws_security_group.alb.id`, `aws_security_group.app.id` and `aws_security_group.db.id`.
- `local.name`, `local.env`, `local.ssm_prefix` and `local.api_host` are shared by all `infra/*.tf` files.
