PROJECT_ID ?= $(shell gcloud config get-value project)
SERVICE_NAME ?= order-decider-2
REGION ?= asia-northeast1
TOPIC_ID ?= local-topic
PORT ?= 1280

# Deploy to Cloud Run from source
deploy:
	@echo "Deploying to Cloud Run..."
	@echo "Project: $(PROJECT_ID)"
	@echo "Region: $(REGION)"
	@echo "Topic: $(TOPIC_ID)"
	gcloud run deploy $(SERVICE_NAME) \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		--source . \
		--allow-unauthenticated \
		--set-env-vars PUBSUB_TOPIC_ID=$(TOPIC_ID) \
		--set-env-vars GOOGLE_CLOUD_PROJECT=$(PROJECT_ID)

# Run locally
dev:
	@echo "Starting local development server on port $(PORT)..."
	@echo "Topic: $(TOPIC_ID)"
	GOOGLE_CLOUD_PROJECT=shingo-ar-gemini-e20251009 \
	.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $(PORT) --reload

# Print help
help:
	@echo "Usage:"
	@echo "  make deploy PROJECT_ID=... TOPIC_ID=..."
	@echo "  make dev    [PORT=1280] [TOPIC_ID=...]"
	@echo ""
	@echo "Variables:"
	@echo "  PROJECT_ID   : GCP Project ID"
	@echo "  SERVICE_NAME : Cloud Run service name"
	@echo "  REGION       : Cloud Run region"
	@echo "  TOPIC_ID     : Pub/Sub Topic ID"
	@echo "  PORT         : Local port (default: 1280)"
