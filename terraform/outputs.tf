# =============================================================================
# Root Outputs
# =============================================================================

# ----- VPC -----
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

# ----- EKS -----
output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}

# ----- ECR -----
output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value       = module.ecr.repository_urls
}

# ----- EC2 -----
output "mongodb_private_ip" {
  description = "MongoDB EC2 private IP (update k8s/mongo.yaml Endpoints with this)"
  value       = module.ec2.mongodb_private_ip
}

output "jenkins_public_ip" {
  description = "Jenkins EC2 public IP"
  value       = module.ec2.jenkins_public_ip
}

output "jenkins_url" {
  description = "Jenkins web UI URL"
  value       = "http://${module.ec2.jenkins_public_ip}:8080"
}
