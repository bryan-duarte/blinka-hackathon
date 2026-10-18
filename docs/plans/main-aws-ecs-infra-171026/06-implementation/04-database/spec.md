# Database Implementation

## Overview

This module defines a single-AZ RDS Postgres 17 instance in the isolated DB subnets. It hosts `blinka_product`, which RDS creates, and `blinka_payments`, which `core.db.bootstrap` creates.

## Files to Modify/Create

- `infra/database.tf` (new): `random_password.db_master`, `aws_db_subnet_group.main`, `aws_db_instance.main`, and `locals { db_url_base = ... }`.
- `infra/versions.tf`: add `random = { source = "hashicorp/random", version = "~> 3.7" }`.

## Implementation Guidelines

```hcl
resource "random_password" "db_master" {
  length  = 32
  special = false # embedded in postgresql:// URLs
}

resource "aws_db_subnet_group" "main" {
  name       = "blinka-db"
  subnet_ids = aws_subnet.db[*].id
}

resource "aws_db_instance" "main" {
  identifier                 = "blinka-prod"
  engine                     = "postgres"
  engine_version             = "17"
  instance_class             = "db.t4g.micro"
  allocated_storage          = 20
  storage_type               = "gp3"
  storage_encrypted          = true
  db_name                    = "blinka_product"
  username                   = "blinka"
  password                   = random_password.db_master.result
  db_subnet_group_name       = aws_db_subnet_group.main.name
  vpc_security_group_ids     = [aws_security_group.db.id]
  publicly_accessible        = false
  multi_az                   = false
  backup_retention_period    = 1
  skip_final_snapshot        = true
  deletion_protection        = false
  apply_immediately          = true
  auto_minor_version_upgrade = true
}

locals {
  db_url_base = "postgresql://${aws_db_instance.main.username}:${random_password.db_master.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}"
}
```

- `engine_version = "17"` lets RDS choose the latest 17.x minor version. If the plan shows a diff on every run, pin the version it resolved (`aws_db_instance.main.engine_version_actual`).
- Don't add a custom parameter group. PG17's default already sets `rds.force_ssl = 1`, which is why the URLs use `sslmode=require`.

## Dependencies

- From module 02: `aws_subnet.db` and `aws_security_group.db`.

## Integration Notes

- Module 05 uses `local.db_url_base` to build:
  - `${local.db_url_base}/blinka_product?sslmode=require`
  - `${local.db_url_base}/blinka_payments?sslmode=require`
- The `db_endpoint` output is `aws_db_instance.main.address`.
- Connection budget: a db.t4g.micro has about 80 `max_connections`, and a single task uses up to about 31. That leaves enough room for one task plus an ECS Exec session.
