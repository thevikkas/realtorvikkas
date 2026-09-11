#!/bin/bash

# Realtor Vikkas Deployment Script
# This script automates deployment to production

set -e

echo "🚀 Realtor Vikkas Deployment Script"
echo "===================================="

# Configuration
SERVER_IP=${1:-""}
DOMAIN=${2:-"realtorvikkas.com"}
APP_DIR="/var/www/realtor-vikkas"
VENV_PATH="$APP_DIR/venv"

if [ -z "$SERVER_IP" ]; then
    echo "Usage: ./deploy.sh <server_ip> [domain]"
    echo "Example: ./deploy.sh 192.168.1.100 realtorvikkas.com"
    exit 1
fi

# Step 1: Connect and prepare server
echo ""
echo "📍 Step 1: Preparing server ($SERVER_IP)..."
ssh -T root@$SERVER_IP << 'REMOTE_COMMANDS'
    set -e

    # Update system
    echo "  • Updating system packages..."
    apt update && apt upgrade -y

    # Install dependencies
    echo "  • Installing dependencies..."
    apt install -y python3.9 python3.9-venv python3-pip nginx certbot python3-certbot-nginx git curl

    # Create application directory
    echo "  • Creating application directory..."
    mkdir -p /var/www/realtor-vikkas
    cd /var/www/realtor-vikkas

    # Setup Python environment
    echo "  • Setting up Python virtual environment..."
    python3.9 -m venv venv
    source venv/bin/activate

    # Verify no external dependencies needed
    echo "  • Verifying zero-dependency setup..."
    pip install --upgrade pip

    echo "  ✅ Server prepared successfully"
REMOTE_COMMANDS

# Step 2: Deploy application
echo ""
echo "📦 Step 2: Deploying application code..."
scp -r ./* root@$SERVER_IP:$APP_DIR/
echo "  ✅ Code deployed"

# Step 3: Initialize application
echo ""
echo "🔧 Step 3: Initializing application..."
ssh -T root@$SERVER_IP << REMOTE_INIT
    set -e
    cd $APP_DIR
    source $VENV_PATH/bin/activate

    # Test import
    echo "  • Testing application import..."
    python3 -c "import app; print('    ✓ App module loaded')"

    # Initialize database (if not exists)
    if [ ! -f "realtor_vikkas.db" ]; then
        echo "  • Initializing database..."
        python3 << 'PYSCRIPT'
from database import init_db
init_db()
print("    ✓ Database initialized")
PYSCRIPT
    fi

    # Set permissions
    chmod 755 $APP_DIR
    chown -R www-data:www-data $APP_DIR

    echo "  ✅ Application initialized"
REMOTE_INIT

# Step 4: Setup systemd service
echo ""
echo "🐚 Step 4: Setting up systemd service..."
ssh -T root@$SERVER_IP << 'REMOTE_SERVICE'
    cat > /etc/systemd/system/realtor-vikkas.service << 'EOF'
[Unit]
Description=Realtor Vikkas Platform
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/realtor-vikkas
Environment="PATH=/var/www/realtor-vikkas/venv/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/var/www/realtor-vikkas/venv/bin/python3 /var/www/realtor-vikkas/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable realtor-vikkas
    systemctl start realtor-vikkas
    sleep 3

    # Check status
    if systemctl is-active --quiet realtor-vikkas; then
        echo "  ✅ Systemd service started successfully"
    else
        echo "  ❌ Service failed to start"
        journalctl -u realtor-vikkas -n 20
        exit 1
    fi
REMOTE_SERVICE

# Step 5: Setup Nginx
echo ""
echo "🌐 Step 5: Configuring Nginx..."
ssh -T root@$SERVER_IP << REMOTE_NGINX
    cat > /etc/nginx/sites-available/realtor-vikkas << 'EOF'
upstream realtor_backend {
    server 127.0.0.1:10000;
    keepalive 32;
}

server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 100M;

    location / {
        proxy_pass http://realtor_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
    }

    location /static/ {
        alias /var/www/realtor-vikkas/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/realtor-vikkas /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    # Test and reload
    nginx -t
    systemctl reload nginx

    echo "  ✅ Nginx configured"
REMOTE_NGINX

# Step 6: Setup SSL
echo ""
echo "🔒 Step 6: Setting up SSL certificate..."
ssh -T root@$SERVER_IP << REMOTE_SSL
    certbot --nginx -d $DOMAIN -d www.$DOMAIN --agree-tos -m admin@$DOMAIN --no-eff-email -n

    echo "  ✅ SSL certificate installed"
REMOTE_SSL

# Step 7: Final verification
echo ""
echo "✅ Step 7: Verifying deployment..."
sleep 5

# Check if server is responding
if curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN | grep -q "200\|301\|302"; then
    echo "  ✅ Website is accessible at https://$DOMAIN"
else
    echo "  ⚠️  Website may not be accessible yet (DNS propagation may take time)"
fi

# Summary
echo ""
echo "🎉 Deployment Complete!"
echo "===================================="
echo ""
echo "✅ Platform Details:"
echo "   Server: $SERVER_IP"
echo "   Domain: https://$DOMAIN"
echo "   Admin: thevikkas@gmail.com / Jerry@1998"
echo ""
echo "📊 Next Steps:"
echo "   1. Update your domain DNS to point to $SERVER_IP (A record)"
echo "   2. Wait for DNS propagation (usually 5-15 minutes)"
echo "   3. Visit https://$DOMAIN to verify"
echo "   4. Login with admin credentials above"
echo "   5. Configure your business settings"
echo ""
echo "📞 Support:"
echo "   Check logs: ssh root@$SERVER_IP 'journalctl -u realtor-vikkas -f'"
echo "   Nginx logs: ssh root@$SERVER_IP 'tail -f /var/log/nginx/access.log'"
echo ""
