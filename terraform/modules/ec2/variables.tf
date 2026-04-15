variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_id" {
  description = "Private subnet ID for MongoDB"
  type        = string
}

variable "public_subnet_id" {
  description = "Public subnet ID for Jenkins"
  type        = string
}

variable "key_pair_name" {
  description = "EC2 key pair name for SSH"
  type        = string
}

variable "mongodb_instance_type" {
  description = "Instance type for MongoDB"
  type        = string
}

variable "jenkins_instance_type" {
  description = "Instance type for Jenkins"
  type        = string
}

variable "jenkins_instance_profile" {
  description = "IAM instance profile name for Jenkins"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed for SSH and Jenkins UI"
  type        = string
}

variable "eks_node_security_group_id" {
  description = "EKS node security group ID (for MongoDB ingress)"
  type        = string
}

variable "eks_cluster_name" {
  description = "EKS cluster name (for Jenkins kubeconfig)"
  type        = string
}

variable "aws_region" {
  description = "AWS region (for Jenkins kubeconfig)"
  type        = string
}

variable "ecr_registry" {
  description = "ECR registry URL"
  type        = string
}
