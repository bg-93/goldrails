provider "google" {
  project               = var.project_id
  region                = var.region
  zone                  = var.zone
  user_project_override = true
  billing_project       = var.project_id
  default_labels        = { app = "gold-rails", env = var.env, managed_by = "terraform" }
}
