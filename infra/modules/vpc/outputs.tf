variable "variables" {
  type = map(any)
}

output "vpc_id" {
  value = var.variables.vpc_id
}

output "public_subnet_ids" {
  value = var.variables.public_subnet_ids
}

output "private_subnet_ids" {
  value = var.variables.private_subnet_ids
}