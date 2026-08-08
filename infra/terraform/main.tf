terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
}

variable "instance_type" {
  description = "EC2 instance type (ARM64)"
  default     = "t4g.small"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to connect to the simulation host over SSH"
  type        = string
}

variable "ami_id" {
  description = "Ubuntu ARM64 AMI ID (Ubuntu 24.04 LTS, arm64)"
  type        = string
  default     = null
}

data "aws_ami" "ubuntu_noble_arm64" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  simulation_name = "gar-sim-${terraform.workspace}"
  resolved_ami_id = coalesce(var.ami_id, data.aws_ami.ubuntu_noble_arm64.id)
}

# ──────────────────────────────────────────────
# Security Group
# ──────────────────────────────────────────────
resource "aws_security_group" "gar_sim" {
  name        = local.simulation_name
  description = "Gapless Agent Runtime simulation host"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_ingress_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ──────────────────────────────────────────────
# EC2 Instance
# ──────────────────────────────────────────────
resource "aws_instance" "gar_sim" {
  ami                    = local.resolved_ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.gar_sim.id]

  user_data = file("${path.module}/user_data.sh")

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name    = local.simulation_name
    Project = "GaplessAgentRuntime"
    Workspace = terraform.workspace
  }
}

# ──────────────────────────────────────────────
# Outputs
# ──────────────────────────────────────────────
output "instance_id" {
  value = aws_instance.gar_sim.id
}

output "public_ip" {
  value = aws_instance.gar_sim.public_ip
}
