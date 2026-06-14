variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type = string
}

variable "cluster_version" {
  type    = string
  default = "1.30"
}

variable "node_instance_type" {
  type    = string
  default = "m7i.xlarge"
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 10
}

variable "node_desired_size" {
  type    = number
  default = 3
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}