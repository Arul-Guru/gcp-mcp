# Lab 04 - Compute Engine, Cloud Scheduler, Logging, Resource Manager
Write-Host "`n== Resource Manager: projects ==" -ForegroundColor Cyan
gcloud projects list --format="table(projectId,name,projectNumber)"
gcloud projects describe floci-local --format="yaml(projectId,name,lifecycleState)"

Write-Host "`n== Compute: networks and zones ==" -ForegroundColor Cyan
gcloud compute networks list --format="table(name,autoCreateSubnetworks)"
gcloud compute zones list --limit=5 --format="table(name,region,status)"
gcloud compute machine-types list --limit=5 --format="table(name,zone,guestCpus,memoryMb)"

Write-Host "`n== Compute: create a VM ==" -ForegroundColor Cyan
gcloud compute instances create lab-vm --zone=us-central1-a --machine-type=e2-micro
gcloud compute instances list --format="table(name,zone,machineType,status,networkInterfaces[0].networkIP)"

Write-Host "`n== Compute: describe, stop, start, delete ==" -ForegroundColor Cyan
gcloud compute instances describe lab-vm --zone=us-central1-a --format="yaml(name,status,machineType)"
gcloud compute instances stop  lab-vm --zone=us-central1-a --quiet
gcloud compute instances list --format="table(name,status)"
gcloud compute instances start lab-vm --zone=us-central1-a --quiet
gcloud compute instances list --format="table(name,status)"

Write-Host "`n== Compute: disks and firewall rules ==" -ForegroundColor Cyan
gcloud compute disks create lab-disk --zone=us-central1-a --size=10GB
gcloud compute disks list --format="table(name,zone,sizeGb,status)"
gcloud compute firewall-rules create lab-allow-http --allow=tcp:80 --description="lab rule"
gcloud compute firewall-rules list --format="table(name,network,allowed[].map().firewall_rule().list())"

Write-Host "`n== Scheduler: create a Pub/Sub cron job ==" -ForegroundColor Cyan
gcloud pubsub topics create lab-cron-topic 2>$null
gcloud scheduler jobs create pubsub lab-nightly --location=us-central1 `
  --schedule="0 2 * * *" --topic=lab-cron-topic --message-body="nightly tick" --time-zone="Etc/UTC"
gcloud scheduler jobs list --location=us-central1 --format="table(name,schedule,state)"
gcloud scheduler jobs describe lab-nightly --location=us-central1 --format="yaml(name,schedule,timeZone,pubsubTarget)"

Write-Host "`n== Scheduler: pause / resume / run now ==" -ForegroundColor Cyan
gcloud scheduler jobs pause  lab-nightly --location=us-central1
gcloud scheduler jobs list --location=us-central1 --format="table(name,state)"
gcloud scheduler jobs resume lab-nightly --location=us-central1
gcloud scheduler jobs run    lab-nightly --location=us-central1
gcloud pubsub subscriptions create lab-cron-sub --topic=lab-cron-topic 2>$null
gcloud scheduler jobs run    lab-nightly --location=us-central1
gcloud pubsub subscriptions pull lab-cron-sub --limit=5 --auto-ack --format="table(message.data)"

Write-Host "`n== Logging ==" -ForegroundColor Cyan
gcloud logging logs list --format="table(name)"
gcloud logging write lab-log "hello from the lab" --severity=INFO
gcloud logging read "logName:lab-log" --limit=5 --format="table(severity,textPayload)"
