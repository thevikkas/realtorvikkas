#!/bin/bash

################################################################################
# Realtor Vikkas Platform v1.0 - Production Deployment Script
#
# Usage: ./deploy.sh [staging|production] [repository-url]
# Example: ./deploy.sh production https://github.com/username/realtorvikkas.git
#
# This script automates the deployment of Realtor Vikkas to a production server
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
REPO_URL="${2:-}"
APP_PORT=8000
APP_DIR="/var/www/realtorvikkas"
APP_USER="www-data"
DOMAIN="realtorvikkas.com"

# Functions
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo -e "\n${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗ ERROR: $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠ WARNING: $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root. Use: sudo ./deploy.sh"
    fi
    print_step "Running as root"
}

# Validate inputs
validate_inputs() {
    if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
        print_error "Environment must be 'staging' or 'production'"
    fi

    if [[ -z "$REPO_URL" ]]; then
        print_error "Repository URL required. Usage: ./deploy.sh $ENVIRONMENT <repo-url>"
    fi

    print_step "Input validation passed"
}

# Check system requirements
check_system() {
    print_header "System Requirements Check"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Install with: apt-get install python3"
    fi
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_info "Python $PYTHON_VERSION found"

    # Check disk space
    AVAILABLE_SPACE=$(df /var | awk 'NR==2 {print $4}')
    if [[ $AVAILABLE_SPACE -lt 1000000 ]]; then
        print_warning "Low disk space: ${AVAILABLE_SPACE}KB available"
    else
        print_step "Sufficient disk space available"
    fi

    # Check memory
    AVAILABLE_MEMORY=$(free -m | awk 'NR==2 {print $7}')
    print_info "Available memory: ${AVAILABLE_MEMORY}MB"
}

# Update system
update_system() {
    print_header "System Update"

    apt-get update || print_warning "apt-get update failed"
    print_step "System package list updated"
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    # Install required packages
    PACKAGES="git nginx curl wget certbot python3-certbot-nginx"

    for package in $PACKAGES; do
        if ! dpkg -l | grep -q "^ii  $package"; then
            print_info "Installing $package..."
            apt-get install -y "$package" > /dev/null 2>&1
        fi
    done

    print_step "Dependencies installed"
}

# Setup application directory
setup_app_dir() {
    print_header "Setting Up Application Directory"

    # Create application directory
    mkdir -p "$APP_DIR"
    print_step "Created $APP_DIR"

    # Create necessary subdirectories
    mkdir -p "$APP_DIR/logs"
    mkdir -p "$APP_DIR/backups"
    print_step "Created subdirectories"
}

# Clone/update repository
setup_repository() {
    print_header "Setting Up Repository"

    if [[ -d "$APP_DIR/.git" ]]; then
        print_info "Repository already exists, pulling latest changes..."
        cd "$APP_DIR"
        git pull origin main || print_warning "Could not pull from remote"
    else
        print_info "Cloning repository..."
        git clone "$REPO_URL" "$APP_DIR" || print_error "Failed to clone repository"
    fi

    print_step "Repository ready"
}

# Setup permissions
setup_permissions() {
    print_header "Setting Up Permissions"

    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    chmod -R 755 "$APP_DIR"
    chmod +x "$APP_DIR/app.py"

    print_step "Permissions configured"
}

# Initialize database
init_database() {
    print_header "Initializing Database"

    cd "$APP_DIR"

    # Check if database exists
    if [[ ! -f "realtorvikkas.db" ]]; then
        print_info "Creating new database..."
        # Database will be created on first run by app.py
    else
        print_info "Database already exists"

        # Backup existing database
        cp "realtorvikkas.db" "backups/realtorvikkas.db.backup.$(date +%s)"
        print_step "Database backed up"
    fi
}

# Setup systemd service
setup_service() {
    print_header "Setting Up Systemd Service"

    cat > /etc/systemd/system/realtorvikkas.service << 'EOF'
[Unit]
Description=Realtor Vikkas Platform v1.0
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/realtorvikkas
ExecStart=/usr/bin/python3 /var/www/realtorvikkas/app.py --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/var/www/realtorvikkas/logs/service.log
StandardError=append:/var/www/realtorvikkas/logs/service.log

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    print_step "Systemd service created"
}

# Start service
start_service() {
    print_header "Starting Service"

    systemctl enable realtorvikkas
    systemctl start realtorvikkas

    sleep 2

    if systemctl is-active --quiet realtorvikkas; then
        print_step "Service started successfully"
    else
        print_error "Failed to start service"
    fi
}

# Setup Nginx
setup_nginx() {
    print_header "Setting Up Nginx"

    cat > /etc/nginx/sites-available/realtorvikkas << 'EOF'
upstream realtorvikkas_app {
    server localhost:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name realtorvikkas.com www.realtorvikkas.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://realtorvikkas_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location /static/ {
        alias /var/www/realtorvikkas/static/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/realtorvikkas /etc/nginx/sites-enabled/

    # Disable default site
    rm -f /etc/nginx/sites-enabled/default

    # Test nginx configuration
    if nginx -t > /dev/null 2>&1; then
        systemctl reload nginx
        print_step "Nginx configured and reloaded"
    else
        print_error "Nginx configuration test failed"
    fi
}

# Setup SSL certificate
setup_ssl() {
    if [[ "$ENVIRONMENT" == "production" ]]; then
        print_header "Setting Up SSL Certificate"

        print_info "Installing Let's Encrypt certificate..."

        # Check if certificate already exists
        if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
            print_info "Certificate already exists, skipping installation"
        else
            certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --agree-tos -m thevikkas@gmail.com --non-interactive \
                || print_warning "SSL certificate installation skipped (may need manual setup)"
        fi

        print_step "SSL certificate ready"
    else
        print_info "Skipping SSL setup for staging environment"
    fi
}

# Setup firewall
setup_firewall() {
    print_header "Setting Up Firewall"

    # Enable UFW
    ufw --force enable > /dev/null 2>&1 || true

    # Allow SSH
    ufw allow 22/tcp > /dev/null 2>&1 || true

    # Allow HTTP
    ufw allow 80/tcp > /dev/null 2>&1 || true

    # Allow HTTPS
    ufw allow 443/tcp > /dev/null 2>&1 || true

    print_step "Firewall configured"
}

# Setup log rotation
setup_log_rotation() {
    print_header "Setting Up Log Rotation"

    cat > /etc/logrotate.d/realtorvikkas << 'EOF'
/var/www/realtorvikkas/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload realtorvikkas > /dev/null 2>&1 || true
    endscript
}
EOF

    print_step "Log rotation configured"
}

# Verify deployment
verify_deployment() {
    print_header "Verifying Deployment"

    # Check service status
    if systemctl is-active --quiet realtorvikkas; then
        print_step "Service is running"
    else
        print_error "Service is not running"
    fi

    # Check Nginx status
    if systemctl is-active --quiet nginx; then
        print_step "Nginx is running"
    else
        print_error "Nginx is not running"
    fi

    # Wait for app to be ready
    print_info "Waiting for application to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/ > /dev/null 2>&1; then
            print_step "Application is responding"
            break
        fi
        sleep 1
    done

    # Check database
    if [[ -f "$APP_DIR/realtorvikkas.db" ]]; then
        print_step "Database exists"
    else
        print_warning "Database file not found"
    fi
}

# Print summary
print_summary() {
    print_header "Deployment Summary"

    cat << EOF

✅ DEPLOYMENT COMPLETE

Environment:     $ENVIRONMENT
Application:     Realtor Vikkas Platform v1.0
Domain:          $DOMAIN
Directory:       $APP_DIR
Port:            $APP_PORT
Service Status:  $(systemctl is-active realtorvikkas)
Nginx Status:    $(systemctl is-active nginx)

📊 Next Steps:

1. Verify all 10 systems are operational
2. Check logs: tail -f $APP_DIR/logs/service.log
3. Monitor performance: grep "SLOW_QUERY" $APP_DIR/performance.log
4. Setup monitoring/alerts (optional)

📞 Support:
   Admin: thevikkas@gmail.com

🎉 Realtor Vikkas Platform v1.0 is now LIVE!

EOF
}

# Main execution
main() {
    print_header "Realtor Vikkas Platform v1.0 - Deployment Script"

    echo -e "${YELLOW}Environment: $ENVIRONMENT${NC}"
    echo -e "${YELLOW}Repository: $REPO_URL${NC}"

    print_info "This deployment will take several minutes..."

    check_root
    validate_inputs
    check_system
    update_system
    install_dependencies
    setup_app_dir
    setup_repository
    setup_permissions
    init_database
    setup_service
    start_service
    setup_nginx
    setup_ssl
    setup_firewall
    setup_log_rotation
    verify_deployment
    print_summary
}

# Run main function
main "$@"
