locals {
  db_master_username = "blinka"
  db_server_url      = "postgresql://${local.db_master_username}:${random_password.db_master.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}"
}

resource "random_password" "db_master" {
  length  = 32
  special = false # embedded verbatim in postgresql:// URLs
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.db[*].id
}

resource "aws_db_instance" "main" {
  identifier                 = "${local.name}-${local.env}"
  engine                     = "postgres"
  engine_version             = "17"
  instance_class             = "db.t4g.micro"
  allocated_storage          = 20
  storage_type               = "gp3"
  storage_encrypted          = true
  db_name                    = "blinka_product"
  username                   = local.db_master_username
  password                   = random_password.db_master.result
  port                       = local.postgres_port
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
