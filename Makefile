.PHONY: setup dev test deploy clean

# Setup project
setup:
	chmod +x setup-project.sh
	./setup-project.sh

# Local development
dev:
	docker-compose up -d
	@echo "Services starting..."
	@echo "API Service: http://localhost:8000"
	@echo "MongoDB: mongodb://admin:password123@localhost:27017"
	@echo "Redis: redis://localhost:6379"

# Stop development services
dev-stop:
	docker-compose down

# Run tests
test:
	python -m pytest tests/ -v

# Generate static audio
audio:
	python audio-generation/scripts/generate_static_audio.py

# Import client data
import-data:
	python scripts/setup/import-client-data.py

# Deploy to AWS
deploy:
	./scripts/deployment/deploy-infrastructure.sh
	./scripts/deployment/deploy-api-service.sh
	./scripts/deployment/deploy-worker-service.sh

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Generate static audio files
audio:
	python audio-generation/scripts/generate_static_audio.py

# Import client data to database
import-data:
	python scripts/setup/import-client-data.py

# Deploy locally with data import and audio generation
deploy-local:
	./scripts/deployment/deploy-local.sh --import-data --generate-audio

# Check service health
health:
	@echo "🔍 Checking API service health..."
	@python ecs-api-service/health-check.py

# View logs
logs:
	docker-compose logs -f

# View specific service logs
logs-api:
	docker-compose logs -f api-service

logs-worker:
	docker-compose logs -f worker-service

# Reset everything (clean data)
reset:
	docker-compose down -v
	docker-compose up -d
	make import-data

# Show service URLs
urls:
	@echo "🌐 Service URLs:"
	@echo "  API Service: http://localhost:8000"
	@echo "  API Health: http://localhost:8000/health"
	@echo "  MongoDB: mongodb://admin:password123@localhost:27017"
	@echo "  Redis: redis://localhost:6379"

# Build services with shared code sync
build:
	./scripts/build-services.sh

# Quick sync shared code
sync-shared:
	./scripts/sync-shared.sh

# Development with sync
dev-build:
	./scripts/build-services.sh
	docker-compose up -d

# Updated development start
dev: sync-shared
	docker-compose up -d
