terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# State: local by default so a fresh clone works with nothing else. For a shared
# project, copy backend.tf.example to backend.tf and point it at a bucket you own.
