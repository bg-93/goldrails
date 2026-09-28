provider "aws" {
  region  = var.region
  profile = var.profile
  default_tags {
    tags = { app = "gold-rails", managed_by = "terraform" }
  }
}
