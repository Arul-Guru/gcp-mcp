# Lab 05 - Compute Engine (emulator-correct ordering)
# The floci catalog stocks only: c3-standard-4, e2-standard-2, g2-standard-4,
# g2-standard-8, n2-standard-4, n2-standard-8  -- and NO networks by default,
# so you must create a network before any instance or firewall rule.
$Z="us-central1-a"; $MT="e2-standard-2"

Write-Host "`n== 1. Inspect the catalog ==" -ForegroundColor Cyan
gcloud compute machine-types list --zones=$Z --format="value(name,guestCpus,memoryMb)"

Write-Host "`n== 2. Create a VPC network + subnet ==" -ForegroundColor Cyan
gcloud compute networks create default --subnet-mode=custom
gcloud compute networks subnets create default-us-central1 `
  --network=default --region=us-central1 --range=10.0.0.0/24
gcloud compute networks list --format="value(name)"
gcloud compute networks subnets list --format="value(name,region,ipCidrRange)"

Write-Host "`n== 3. Firewall rules ==" -ForegroundColor Cyan
gcloud compute firewall-rules create lab-allow-http --network=default --allow=tcp:80
gcloud compute firewall-rules create lab-allow-ssh  --network=default --allow=tcp:22 --source-ranges=10.0.0.0/8
gcloud compute firewall-rules list --format="value(name,network,allowed[0].IPProtocol,allowed[0].ports[0])"

Write-Host "`n== 4. Create a VM ==" -ForegroundColor Cyan
# The emulator's IMAGE catalog is empty, so gcloud's default boot image
# (debian-cloud/debian-12) 404s. Create a disk and boot from it instead.
# Note: --labels value is QUOTED -- an unquoted comma is PowerShell's array operator.
gcloud compute disks create lab-boot --zone=$Z --size=10GB
gcloud compute instances create lab-vm --zone=$Z --machine-type=$MT `
  --subnet=default-us-central1 --disk="name=lab-boot,boot=yes,auto-delete=no" `
  --labels="env=lab,owner=arul"
gcloud compute instances list --format="value(name,status)"

Write-Host "`n== 5. Describe it ==" -ForegroundColor Cyan
gcloud compute instances describe lab-vm --zone=$Z --format="yaml(name,status,labels,networkInterfaces)"

Write-Host "`n== 6. Lifecycle: stop -> start -> reset ==" -ForegroundColor Cyan
gcloud compute instances stop  lab-vm --zone=$Z --quiet
gcloud compute instances list --format="value(name,status)"
gcloud compute instances start lab-vm --zone=$Z --quiet
gcloud compute instances list --format="value(name,status)"

Write-Host "`n== 7. Attach a disk ==" -ForegroundColor Cyan
gcloud compute disks create lab-data --zone=$Z --size=10GB
gcloud compute instances attach-disk lab-vm --zone=$Z --disk=lab-data
gcloud compute instances describe lab-vm --zone=$Z --format="value(disks[].deviceName)"

Write-Host "`n== 8. Labels and tags ==" -ForegroundColor Cyan
gcloud compute instances add-labels lab-vm --zone=$Z --labels="tier=backend"
gcloud compute instances describe lab-vm --zone=$Z --format="yaml(labels)"

Write-Host "`n== 9. Tear down ==" -ForegroundColor Cyan
gcloud compute instances delete lab-vm --zone=$Z --quiet
gcloud compute instances list --format="value(name)"
