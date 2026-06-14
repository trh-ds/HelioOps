variable "region" {
  type    = string
  default = "us-east-1"
}

variable "cidr" {
  type    = string
  default = "10.1.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

module "vpc" {
  source      = "../../modules/vpc"
  region      = var.region
  cidr        = var.cidr
  environment = "production"
  availability_zones = var.availability_zones
}

module "eks" {
  source = "../../modules/eks-cluster"

  environment        = "production"
  cluster_version    = "1.30"
  node_instance_type = "m7i.xlarge"
  node_min_size      = 3
  node_max_size      = 20
  node_desired_size  = 5
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  value = module.eks.kubeconfig_command
}