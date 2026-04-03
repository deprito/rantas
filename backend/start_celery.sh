#!/bin/bash
# Celery worker startup script for PhishTrack
# Starts the worker with ALL required queues to ensure tasks are processed

celery -A app.tasks.celery_app worker \
  --loglevel=info \
  --pool=solo \
  -Q phishtrack,phishtrack.osint,phishtrack.email,phishtrack.monitor,phishtrack.evidence
