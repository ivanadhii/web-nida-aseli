# Makefile for Sensor Monitoring Docker Setup

.PHONY: help build up down restart logs clean status health test

# Default target
help:
	@echo "🌊 Arjasari Sensor Monitoring - Docker Commands"
	@echo ""
	@echo "📦 Build & Deploy:"
	@echo "  build          Build all Docker images"
	@echo "  up             Start all services (build if needed)"
	@echo "  down           Stop and remove all services"
	@echo "  restart        Restart all services"
	@echo ""
	@echo "📊 Access Points:"
	@echo "  dashboard      Open dashboard (Port 8080)"
	@echo "  api            Test API (Port 5000)"
	@echo "  adminer        Open database admin (Port 8081)"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  logs           Show logs from all services"
	@echo "  logs-mqtt      Show MQTT worker logs"
	@echo "  logs-api       Show Web API logs"
	@echo "  logs-dashboard Show Dashboard logs"
	@echo "  status         Show service status"
	@echo "  health         Check service health"
	@echo ""
	@echo "🔧 Maintenance:"
	@echo "  clean          Clean up containers, images, and volumes"
	@echo "  clean-all      Clean everything including data"
	@echo "  backup         Backup database"
	@echo "  restore        Restore database from backup"
	@echo ""
	@echo "🧪 Development:"
	@echo "  test           Run basic functionality tests"
	@echo "  shell-mqtt     Shell into MQTT worker container"
	@echo "  shell-api      Shell into Web API container"
	@echo "  db-shell       Open database shell"

# Build all images
build:
	@echo "🏗️ Building Docker images..."
	docker-compose build

# Start services
up:
	@echo "🚀 Starting Sensor Monitoring services..."
	@mkdir -p data logs/mqtt logs/api
	docker-compose up -d --build
	@echo "✅ Services started!"
	@echo "📊 Dashboard: http://localhost:8080"
	@echo "🔌 API: http://localhost:5000/api"
	@echo "🗄️ Adminer: http://localhost:8081 (run 'make admin' to enable)"
	@echo ""
	@echo "🌐 Cloudflare Tunnel Ports to expose:"
	@echo "  - Port 8080 (Dashboard)"
	@echo "  - Port 5000 (API)"
	@echo "  - Port 8081 (Database Admin - Optional)"

# Stop services
down:
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✅ Services stopped!"

# Restart services
restart: down up

# Show logs
logs:
	docker-compose logs -f

logs-mqtt:
	docker-compose logs -f mqtt-worker

logs-api:
	docker-compose logs -f web-api

logs-dashboard:
	docker-compose logs -f dashboard

# Show service status
status:
	@echo "📊 Service Status:"
	@docker-compose ps
	@echo ""
	@echo "🐳 Container Health:"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Quick access commands
dashboard:
	@echo "🌐 Opening Dashboard..."
	@xdg-open http://localhost:8080 2>/dev/null || open http://localhost:8080 2>/dev/null || echo "Dashboard: http://localhost:8080"

api:
	@echo "🔌 Testing API..."
	@curl -s http://localhost:5000/api/health | jq . || echo "API: http://localhost:5000/api"

adminer:
	@echo "🗄️ Opening Database Admin..."
	@docker-compose --profile admin up -d
	@xdg-open http://localhost:8081 2>/dev/null || open http://localhost:8081 2>/dev/null || echo "Adminer: http://localhost:8081"

# Health check
health:
	@echo "🩺 Health Check:"
	@echo "  API Health: $(curl -s http://localhost:5000/api/health | jq -r '.status // "ERROR"' 2>/dev/null || echo "ERROR")"
	@echo "  Dashboard: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/ 2>/dev/null || echo "ERROR")"
	@echo "  Database: $(docker-compose exec -T mqtt-worker python -c 'import sqlite3; conn = sqlite3.connect("/app/data/sensor_monitoring.db"); print("OK"); conn.close()' 2>/dev/null || echo "ERROR")"

# Clean up
clean:
	@echo "🧹 Cleaning up containers and images..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ Cleanup completed!"

clean-all: clean
	@echo "🗑️ Removing all data..."
	sudo rm -rf data logs
	@echo "✅ All data removed!"

# Backup database
backup:
	@echo "💾 Creating database backup..."
	@mkdir -p backups
	@backup_file="backups/sensor_monitoring_$$(date +%Y%m%d_%H%M%S).db"
	@docker-compose exec -T mqtt-worker cp /app/data/sensor_monitoring.db /tmp/backup.db
	@docker cp $$(docker-compose ps -q mqtt-worker):/tmp/backup.db $$backup_file
	@echo "✅ Database backed up to: $$backup_file"

# Restore database
restore:
	@echo "📥 Restoring database..."
	@read -p "Enter backup file path: " backup_file; \
	if [ -f "$$backup_file" ]; then \
		docker cp "$$backup_file" $$(docker-compose ps -q mqtt-worker):/app/data/sensor_monitoring.db; \
		echo "✅ Database restored from: $$backup_file"; \
	else \
		echo "❌ Backup file not found: $$backup_file"; \
	fi

# Enable admin tools
admin:
	@echo "🔧 Starting admin tools..."
	docker-compose --profile admin up -d
	@echo "🗄️ Adminer available at: http://localhost:8080"

# Run tests
test:
	@echo "🧪 Running basic functionality tests..."
	@echo "Testing API endpoints..."
	@curl -s http://localhost:5000/api/health | jq . 2>/dev/null || echo "API health check failed"
	@curl -s http://localhost:5000/api/latest | jq '.success' 2>/dev/null || echo "API latest data failed"
	@echo "Testing Dashboard..."
	@curl -s -o /dev/null -w "Dashboard HTTP Status: %{http_code}\n" http://localhost:8080/ 2>/dev/null || echo "Dashboard test failed"
	@echo "✅ Basic tests completed!"

# Development shells
shell-mqtt:
	docker-compose exec mqtt-worker /bin/bash

shell-api:
	docker-compose exec web-api /bin/bash

shell-dashboard:
	docker-compose exec dashboard /bin/sh

# Database shell
db-shell:
	docker-compose exec mqtt-worker sqlite3 /app/data/sensor_monitoring.db

# Monitor resources
monitor:
	@echo "📈 Resource Monitoring:"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Show configuration
config:
	@echo "⚙️ Docker Compose Configuration:"
	docker-compose config