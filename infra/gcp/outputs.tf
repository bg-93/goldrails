output "instance" { value = google_compute_instance.serve.name }
output "zone" { value = var.zone }
output "tunnel_commands" {
  description = "One IAP tunnel per model; then point KEV_URL / OPENJEV_URL at localhost."
  value = [for m in var.models :
    "gcloud compute start-iap-tunnel ${google_compute_instance.serve.name} ${m.port} --local-host-port=localhost:${m.port} --zone ${var.zone} --project ${var.project_id}   # ${m.name}"
  ]
}
output "ssh" { value = "gcloud compute ssh ${google_compute_instance.serve.name} --zone ${var.zone} --project ${var.project_id} --tunnel-through-iap" }

output "project" {
  value = var.project_id
}
