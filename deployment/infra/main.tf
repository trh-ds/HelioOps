# HelioOps backend on a single EC2 box.
#
# Shape: ECR holds the image, one instance runs docker compose (API + Caddy),
# an Elastic IP gives the DNS record something stable to point at. No load
# balancer — an ALB is ~$16/mo and there is exactly one target, because
# pipeline.py:58 keeps results in a process-local dict and a second instance
# would 404 /api/result/{id} half the time.
#
#   terraform init
#   terraform apply -var-file=environments/prod/terraform.tfvars

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "terraform"
    }
  }
}

# Default VPC on purpose. One public box needs no private subnets, no NAT
# gateway ($32/mo) and no route table of its own.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# ── Image registry ───────────────────────────────────────────────────────────

resource "aws_ecr_repository" "backend" {
  name                 = var.name
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# The image is ~3 GB. Without this, every CI push accumulates one forever.
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images; older ones are only a rollback target."
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ── Secret ───────────────────────────────────────────────────────────────────

# Created empty and never updated by Terraform: a real value passed through a
# variable lands in the state file in plaintext. Set it out of band with
#   aws ssm put-parameter --name /helioops/groq_api_key --type SecureString \
#     --value gsk_... --overwrite
resource "aws_ssm_parameter" "groq_api_key" {
  name  = "/${var.name}/groq_api_key"
  type  = "SecureString"
  value = "placeholder-set-me-with-the-cli"

  lifecycle {
    ignore_changes = [value]
  }
}

# ── Network ──────────────────────────────────────────────────────────────────

resource "aws_security_group" "instance" {
  name        = "${var.name}-instance"
  description = "HelioOps API: public HTTPS, no SSH."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP - Caddy redirects to HTTPS and serves the ACME HTTP-01 challenge"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS - REST and /ws/stream"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # No port 22. Shell access is SSM Session Manager, which needs no inbound
  # rule, no key pair to lose, and logs who connected:
  #   aws ssm start-session --target <instance-id>
  egress {
    description = "Outbound to Groq, ECR, Let's Encrypt"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── Instance ─────────────────────────────────────────────────────────────────

resource "aws_instance" "backend" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.instance.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user_data.sh", {
    region       = var.region
    name         = var.name
    image        = "${aws_ecr_repository.backend.repository_url}:latest"
    domain       = var.domain
    cors_origins = var.cors_origins
    param_path   = aws_ssm_parameter.groq_api_key.name
  })

  root_block_device {
    volume_size = var.root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  tags = { Name = "${var.name}-backend" }
}

# Separate from the instance so `user_data_replace_on_change` can rebuild the
# box without the DNS record going stale.
resource "aws_eip" "backend" {
  instance = aws_instance.backend.id
  domain   = "vpc"
  tags     = { Name = "${var.name}-backend" }
}
