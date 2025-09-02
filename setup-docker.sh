#!/bin/bash
# setup-docker.sh - One-click Docker setup for Sensor Monitoring

set -e

echo "🌊 Arjasari Sensor Monitoring - Docker Setup"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is installed
check_docker() {
    log_info "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        log_warning "Docker not found. Installing Docker..."
        
        # Install Docker
        sudo apt-get update
        sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
        
        # Add Docker GPG key
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # Add Docker repository
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker Engine
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io
        
        # Add user to docker group
        sudo usermod -aG docker $USER
        
        log_success "Docker installed successfully"
        log_warning "You may need to log out and back in for group changes to take effect"
    else
        log_success "Docker is already installed"
    fi
}

# Check if Docker Compose is installed
check_docker_compose() {
    log_info "Checking Docker Compose installation..."
    
    if ! command -v docker-compose &> /dev/null; then
        log_warning "Docker Compose not found. Installing..."
        
        # Install Docker Compose
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        
        log_success "Docker Compose installed successfully"
    else
        log_success "Docker Compose is already installed"
    fi
}

# Create directory structure
create_directories() {
    log_info "Creating directory structure..."
    
    mkdir -p data
    mkdir -p logs/mqtt
    mkdir -p logs/api
    mkdir -p backups
    mkdir -p dashboard
    
    log_success "Directory structure created"
}

# Set permissions
set_permissions() {
    log_info "Setting proper permissions..."
    
    # Make scripts executable
    chmod +x entrypoint.sh 2>/dev/null || true
    
    # Set data directory permissions
    chmod 755 data
    chmod 755 logs
    
    log_success "Permissions set"
}

# Validate configuration
validate_config() {
    log_info "Validating configuration..."
    
    # Check required files
    required_files=(
        "docker-compose.yml"
        "Dockerfile.mqtt-worker"
        "Dockerfile.web-api" 
        "Dockerfile.dashboard"
        "mqtt_worker.py"
        "web_api.py"
        "pzem_parser.py"
        "dashboard/index.html"
        "requirements.txt"
    )
    
    missing_files=()
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        log_error "Missing required files:"
        printf '%s\n' "${missing_files[@]}"
        exit 1
    fi
    
    log_success "All required files present"
}

# Create .env file if not exists
create_env_file() {
    if [ ! -f ".env" ]; then
        log_info "Creating .env file..."
        
        cat > .env << EOF
# MQTT Configuration
MQTT_BROKER=mqtt.gatevans.com
MQTT_PORT=1883
MQTT_KEEPALIVE=60

# Database Configuration
DB_PATH=/app/data/sensor_monitoring.db
DB_CLEANUP_DAYS=30

# API Configuration
FLASK_ENV=production
FLASK_APP=web_api.py
API_HOST=0.0.0.0
API_PORT=5000

# Dashboard Configuration
DASHBOARD_TITLE=Arjasari Sensor Monitoring

# Docker Configuration
COMPOSE_PROJECT_NAME=sensor-monitoring
DOCKER_BUILDKIT=1

# Logging Configuration
LOG_LEVEL=INFO
EOF
        
        log_success ".env file created"
    else
        log_info ".env file already exists"
    fi
}

# Build and start services
start_services() {
    log_info "Building and starting services..."
    
    # Pull base images first
    log_info "Pulling base images..."
    docker pull python:3.11-slim
    docker pull nginx:alpine
    
    # Build and start services
    log_info "Building application images..."
    docker-compose build
    
    log_info "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Check service health
    for i in {1..30}; do
        if curl -s http://localhost:8080/ >/dev/null 2>&1 && curl -s http://localhost:5000/api/health >/dev/null 2>&1; then
            log_success "Services are ready!"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo
}

# Display access information
show_access_info() {
    echo
    echo "🎉 Setup completed successfully!"
    echo "================================="
    echo
    echo "📊 Access Points:"
    echo "  Dashboard:  http://localhost:8080"
    echo "  API:        http://localhost:5000/api"
    echo "  Health:     http://localhost:5000/api/health"
    echo
    echo "🌐 Cloudflare Tunnel Ports:"
    echo "  - Port 8080 (Dashboard) - Main UI"
    echo "  - Port 5000 (API) - Backend API"  
    echo "  - Port 8081 (Adminer) - Optional DB Admin"
    echo
    echo "🐳 Container Status:"
    docker-compose ps
    echo
    echo "📋 Useful Commands:"
    echo "  View logs:        docker-compose logs -f"
    echo "  Stop services:    docker-compose down"
    echo "  Restart:          docker-compose restart"
    echo "  Health check:     make health"
    echo "  Open dashboard:   make dashboard"
    echo "  Test API:         make api"
    echo
    echo "📁 Important Directories:"
    echo "  Database:   ./data/sensor_monitoring.db"
    echo "  Logs:       ./logs/"
    echo "  Backups:    ./backups/"
    echo
}

# Test services
test_services() {
    log_info "Testing services..."
    
    # Test API
    if curl -s http://localhost:5000/api/health | grep -q "healthy"; then
        log_success "API is responding on port 5000"
    else
        log_warning "API health check failed"
    fi
    
    # Test Dashboard
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ | grep -q "200"; then
        log_success "Dashboard is accessible on port 8080"
    else
        log_warning "Dashboard accessibility check failed"
    fi
    
    # Test database
    if docker-compose exec -T mqtt-worker python -c "import sqlite3; conn = sqlite3.connect('/app/data/sensor_monitoring.db'); conn.close(); print('OK')" 2>/dev/null | grep -q "OK"; then
        log_success "Database is accessible"
    else
        log_warning "Database accessibility check failed"
    fi
}

# Cleanup function for errors
cleanup_on_error() {
    log_error "Setup failed. Cleaning up..."
    docker-compose down 2>/dev/null || true
    exit 1
}

# Main setup function
main() {
    echo
    log_info "Starting Docker setup for Sensor Monitoring..."
    echo
    
    # Set trap for cleanup on error
    trap cleanup_on_error ERR
    
    # Run setup steps
    check_docker
    check_docker_compose
    validate_config
    create_directories
    create_env_file
    set_permissions
    start_services
    test_services
    show_access_info
    
    log_success "🎉 Docker setup completed successfully!"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --clean        Clean up before setup"
        echo "  --dev          Setup for development (with hot reload)"
        echo
        exit 0
        ;;
    --clean)
        log_info "Cleaning up existing setup..."
        docker-compose down -v 2>/dev/null || true
        sudo rm -rf data logs backups
        docker system prune -f
        log_success "Cleanup completed"
        ;;
    --dev)
        log_info "Setting up for development..."
        export FLASK_ENV=development
        export LOG_LEVEL=DEBUG
        ;;
esac

# Run main setup
main