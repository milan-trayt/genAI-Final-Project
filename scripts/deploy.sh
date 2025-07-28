#!/bin/bash

# GenAI DevOps Assistant Deployment Script
# This script handles deployment for different environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT=${1:-development}
COMPOSE_FILES=""

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    echo "Usage: $0 [environment] [command]"
    echo ""
    echo "Environments:"
    echo "  development  - Development environment with hot reload"
    echo "  production   - Production environment with optimizations"
    echo "  testing      - Testing environment"
    echo ""
    echo "Commands:"
    echo "  up           - Start services (default)"
    echo "  down         - Stop services"
    echo "  restart      - Restart services"
    echo "  logs         - Show logs"
    echo "  status       - Show service status"
    echo "  clean        - Clean up containers and volumes"
    echo "  build        - Build images"
    echo "  ingestion    - Run knowledge ingestion"
    echo ""
    echo "Examples:"
    echo "  $0 development up"
    echo "  $0 production restart"
    echo "  $0 development ingestion"
}

check_requirements() {
    log_info "Checking requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_warning ".env file not found. Creating from template..."
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        log_warning "Please edit .env file with your configuration before continuing."
        exit 1
    fi
    
    log_success "Requirements check passed"
}

setup_compose_files() {
    COMPOSE_FILES="-f docker-compose.yml"
    
    case $ENVIRONMENT in
        development)
            COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.dev.yml"
            ;;
        production)
            COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.prod.yml"
            ;;
        testing)
            COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.test.yml"
            ;;
        *)
            log_error "Unknown environment: $ENVIRONMENT"
            show_usage
            exit 1
            ;;
    esac
    
    log_info "Using compose files: $COMPOSE_FILES"
}

create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p "$PROJECT_ROOT/data"
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/ssl"
    
    # Set permissions
    chmod 755 "$PROJECT_ROOT/data"
    chmod 755 "$PROJECT_ROOT/logs"
    
    log_success "Directories created"
}

build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    docker-compose $COMPOSE_FILES build --no-cache
    
    log_success "Images built successfully"
}

start_services() {
    log_info "Starting services in $ENVIRONMENT environment..."
    
    cd "$PROJECT_ROOT"
    
    # Start core services
    docker-compose $COMPOSE_FILES up -d redis backend frontend
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    check_service_health
    
    # Start additional services based on environment
    if [ "$ENVIRONMENT" = "production" ]; then
        docker-compose $COMPOSE_FILES --profile production up -d
        docker-compose $COMPOSE_FILES --profile monitoring up -d
    fi
    
    log_success "Services started successfully"
    show_service_status
}

stop_services() {
    log_info "Stopping services..."
    
    cd "$PROJECT_ROOT"
    docker-compose $COMPOSE_FILES down
    
    log_success "Services stopped"
}

restart_services() {
    log_info "Restarting services..."
    stop_services
    start_services
}

show_logs() {
    cd "$PROJECT_ROOT"
    docker-compose $COMPOSE_FILES logs -f --tail=100
}

show_service_status() {
    log_info "Service Status:"
    cd "$PROJECT_ROOT"
    docker-compose $COMPOSE_FILES ps
}

check_service_health() {
    log_info "Checking service health..."
    
    # Check Redis
    if docker-compose $COMPOSE_FILES exec -T redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis is healthy"
    else
        log_error "Redis is not healthy"
    fi
    
    # Check Backend
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Backend is healthy"
    else
        log_warning "Backend health check failed (may still be starting)"
    fi
    
    # Check Frontend
    if curl -f http://localhost:8501/_stcore/health > /dev/null 2>&1; then
        log_success "Frontend is healthy"
    else
        log_warning "Frontend health check failed (may still be starting)"
    fi
}

clean_up() {
    log_warning "This will remove all containers, networks, and volumes. Are you sure? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        cd "$PROJECT_ROOT"
        
        # Stop and remove containers
        docker-compose $COMPOSE_FILES down -v --remove-orphans
        
        # Remove images
        docker-compose $COMPOSE_FILES down --rmi all
        
        # Clean up Docker system
        docker system prune -f
        
        log_success "Cleanup completed"
    else
        log_info "Cleanup cancelled"
    fi
}

run_ingestion() {
    log_info "Running knowledge ingestion..."
    
    cd "$PROJECT_ROOT"
    
    # Start ingestion service
    docker-compose $COMPOSE_FILES --profile ingestion run --rm ingestion python3 interactive_ingestion.py --interactive
    
    log_success "Knowledge ingestion completed"
}

backup_data() {
    log_info "Creating backup..."
    
    BACKUP_DIR="$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup Redis data
    docker-compose $COMPOSE_FILES exec -T redis redis-cli BGSAVE
    docker cp "$(docker-compose $COMPOSE_FILES ps -q redis)":/data/dump.rdb "$BACKUP_DIR/"
    
    # Backup application data
    cp -r "$PROJECT_ROOT/data" "$BACKUP_DIR/"
    
    # Backup logs
    cp -r "$PROJECT_ROOT/logs" "$BACKUP_DIR/"
    
    log_success "Backup created at $BACKUP_DIR"
}

# Main execution
main() {
    local command=${2:-up}
    
    # Show usage if help requested
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        show_usage
        exit 0
    fi
    
    log_info "GenAI DevOps Assistant Deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Command: $command"
    
    check_requirements
    setup_compose_files
    create_directories
    
    case $command in
        up|start)
            start_services
            ;;
        down|stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs
            ;;
        status)
            show_service_status
            ;;
        clean)
            clean_up
            ;;
        build)
            build_images
            ;;
        ingestion)
            run_ingestion
            ;;
        backup)
            backup_data
            ;;
        health)
            check_service_health
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"