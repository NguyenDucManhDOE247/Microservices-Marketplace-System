terraform {
  backend "s3" {
    bucket       = "osm-terraform-state-825621302666"
    key          = "infrastructure/terraform.tfstate"
    region       = "ap-southeast-1"
    use_lockfile = true
    encrypt      = true
  }
}
