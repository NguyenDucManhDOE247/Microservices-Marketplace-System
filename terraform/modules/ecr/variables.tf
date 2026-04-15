variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "services" {
  description = "List of microservice names"
  type        = list(string)
}
