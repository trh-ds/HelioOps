variable "region" {
  type    = string
  default = "us-east-1"
}

variable "cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

module "vpc" {
  source      = "../../modules/vpc"
  region      = var.region
  cidr        = var.cidr
  environment = "staging"
  availability_zones = var.availability_zones
}

module "eks" {
  source = "../../modules/eks-cluster"

  environment        = "staging"
  cluster_version    = "1.30"
  node_instance_type = "m7i.large"
  node_min_size      = 2
  node_max_size      = 6
  node_desired_size  = 2
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  value = module.eks.kubeconfig_command
}