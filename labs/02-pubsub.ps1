# Lab 02 - Pub/Sub
$T="lab-orders"; $DLQ="lab-orders-dlq"; $S="lab-orders-sub"; $PULL="lab-orders-pull"

Write-Host "`n== 1. Create topics ==" -ForegroundColor Cyan
gcloud pubsub topics create $T
gcloud pubsub topics create $DLQ

Write-Host "`n== 2. Subscription with ack deadline + retention ==" -ForegroundColor Cyan
gcloud pubsub subscriptions create $S --topic=$T --ack-deadline=30 --message-retention-duration=10m

Write-Host "`n== 3. Second subscription = fan-out (each gets its own copy) ==" -ForegroundColor Cyan
gcloud pubsub subscriptions create $PULL --topic=$T

Write-Host "`n== 4. Publish with attributes and an ordering key ==" -ForegroundColor Cyan
gcloud pubsub topics publish $T --message='{"id":1,"item":"widget"}' --attribute=source=lab,priority=high
gcloud pubsub topics publish $T --message='{"id":2,"item":"gizmo"}'  --attribute=source=lab,priority=low

Write-Host "`n== 5. Pull WITHOUT auto-ack (message stays outstanding) ==" -ForegroundColor Cyan
gcloud pubsub subscriptions pull $S --limit=2 --format="table(message.data,message.attributes,ackId.scope(1))"

Write-Host "`n== 6. Fan-out proof: the other sub still has both messages ==" -ForegroundColor Cyan
gcloud pubsub subscriptions pull $PULL --limit=2 --auto-ack --format="table(message.data,message.attributes)"

Write-Host "`n== 7. Describe + list ==" -ForegroundColor Cyan
gcloud pubsub subscriptions describe $S --format="yaml(name,topic,ackDeadlineSeconds,messageRetentionDuration)"
gcloud pubsub topics list --format="table(name)"

Write-Host "`n== 8. List subscriptions attached to a topic ==" -ForegroundColor Cyan
gcloud pubsub topics list-subscriptions $T

Write-Host "`n== 9. Update ack deadline ==" -ForegroundColor Cyan
gcloud pubsub subscriptions update $S --ack-deadline=60
gcloud pubsub subscriptions describe $S --format="value(ackDeadlineSeconds)"

Write-Host "`n== 10. Dead-letter wiring ==" -ForegroundColor Cyan
gcloud pubsub subscriptions update $S --dead-letter-topic=$DLQ --max-delivery-attempts=5
gcloud pubsub subscriptions describe $S --format="yaml(deadLetterPolicy)"
