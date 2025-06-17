#!/usr/bin/env python3
"""
VPK (Vast Password Kracker) Production Setup Script

This script helps configure VPK for production deployment with:
- Environment variables generation
- SSL certificate setup  
- Database configuration
- Security key generation
- Docker deployment assistance
"""

import os
import sys
import secrets
import string
import subprocess
import re
import json
from pathlib import Path
from typing import Dict, Optional
import base64

class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_banner():
    """Print VPK setup banner"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                    VPK Production Setup                      ║
║                  Vast Password Kracker v1.0                  ║
║                                                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}

{Colors.YELLOW}This script will help you configure VPK for production deployment.{Colors.END}
{Colors.WHITE}Please follow the prompts to set up your environment.{Colors.END}

"""
    print(banner)

def generate_secret_key(length: int = 64) -> str:
    """Generate a cryptographically secure secret key"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_settings_key() -> str:
    """Generate a Fernet-compatible encryption key"""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_domain(domain: str) -> bool:
    """Validate domain format"""
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    
    # Additional checks
    if not re.match(pattern, domain):
        return False
    
    # Check overall length (253 chars max for FQDN)
    if len(domain) > 253:
        return False
    
    # Check each label doesn't exceed 63 chars and doesn't start/end with hyphen
    labels = domain.split('.')
    for label in labels:
        if len(label) > 63 or label.startswith('-') or label.endswith('-'):
            return False
    
    return True

def prompt_input(message: str, default: str = "", validator=None, sensitive: bool = False) -> str:
    """Get user input with validation"""
    while True:
        if default:
            prompt = f"{Colors.WHITE}{message} [{Colors.CYAN}{default}{Colors.WHITE}]: {Colors.END}"
        else:
            prompt = f"{Colors.WHITE}{message}: {Colors.END}"
        
        if sensitive:
            import getpass
            value = getpass.getpass(prompt)
        else:
            value = input(prompt).strip()
        
        if not value and default:
            value = default
        
        if not value:
            print(f"{Colors.RED}This field is required.{Colors.END}")
            continue
        
        if validator and not validator(value):
            print(f"{Colors.RED}Invalid format. Please try again.{Colors.END}")
            continue
        
        return value

def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Get yes/no input from user"""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{Colors.WHITE}{message} [{default_str}]: {Colors.END}").strip().lower()
        
        if not response:
            return default
        
        if response in ['y', 'yes', 'true', '1']:
            return True
        elif response in ['n', 'no', 'false', '0']:
            return False
        else:
            print(f"{Colors.RED}Please enter y/yes or n/no{Colors.END}")

def check_docker():
    """Check if Docker and Docker Compose are installed"""
    print(f"{Colors.BLUE}Checking Docker installation...{Colors.END}")
    
    try:
        # Check Docker
        result = subprocess.run(['sudo', 'docker', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{Colors.RED}❌ Docker is not installed or not accessible with sudo{Colors.END}")
            return False
        print(f"{Colors.GREEN}✅ Docker: {result.stdout.strip()}{Colors.END}")
        
        # Check Docker Compose
        result = subprocess.run(['sudo', 'docker', 'compose', 'version'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{Colors.RED}❌ Docker Compose is not installed or not available{Colors.END}")
            return False
        print(f"{Colors.GREEN}✅ Docker Compose: {result.stdout.strip()}{Colors.END}")
        
        return True
    except FileNotFoundError:
        print(f"{Colors.RED}❌ Docker is not installed{Colors.END}")
        return False

def collect_config() -> Dict[str, str]:
    """Collect configuration from user"""
    config = {}
    
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔧 Basic Configuration{Colors.END}")
    print(f"{Colors.YELLOW}Let's configure the basic settings for your VPK deployment.{Colors.END}\n")
    
    # Domain configuration
    config['DOMAIN'] = prompt_input(
        "Enter your domain name (e.g., vpk.example.com)",
        validator=validate_domain
    )
    
    # SSL Configuration
    config['USE_SSL'] = str(prompt_yes_no(
        "Do you want to enable SSL/HTTPS?", 
        default=True
    )).lower()
    
    if config['USE_SSL'] == 'true':
        print(f"\n{Colors.YELLOW}Manual SSL Setup Required:{Colors.END}")
        print(f"{Colors.WHITE}You will need to place your SSL certificates in:{Colors.END}")
        print(f"{Colors.CYAN}  - docker/certs/fullchain.pem (certificate chain){Colors.END}")
        print(f"{Colors.CYAN}  - docker/certs/privkey.pem (private key){Colors.END}")
        print(f"{Colors.WHITE}These files must be in place before starting the services.{Colors.END}")
    
    # Database configuration
    print(f"\n{Colors.BOLD}{Colors.BLUE}🗄️  Database Configuration{Colors.END}")
    config['POSTGRES_USER'] = prompt_input("PostgreSQL username", default="vpk")
    config['POSTGRES_PASSWORD'] = prompt_input("PostgreSQL password", sensitive=True) or generate_secret_key(16)
    config['POSTGRES_DB'] = prompt_input("PostgreSQL database name", default="vpk_db")
    
    # Security keys
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔐 Security Configuration{Colors.END}")
    print(f"{Colors.YELLOW}Generating secure encryption keys...{Colors.END}")
    
    config['SECRET_KEY'] = generate_secret_key(64)
    config['SETTINGS_ENCRYPTION_KEY'] = generate_settings_key()
    
    print(f"{Colors.GREEN}✅ Security keys generated{Colors.END}")
    
    # API Configuration
    if config['USE_SSL'] == 'true':
        config['NEXT_PUBLIC_API_URL'] = f"https://{config['DOMAIN']}"
        # Set CORS origins for HTTPS
        cors_origins = [
            f"https://{config['DOMAIN']}",
            f"https://www.{config['DOMAIN']}"
        ]
    else:
        config['NEXT_PUBLIC_API_URL'] = f"http://{config['DOMAIN']}"
        # Set CORS origins for HTTP
        cors_origins = [
            f"http://{config['DOMAIN']}",
            f"http://www.{config['DOMAIN']}"
        ]
    
    # Store CORS origins as JSON string
    config['BACKEND_CORS_ORIGINS'] = json.dumps(cors_origins)
    
    # Optional: Resource limits
    print(f"\n{Colors.BOLD}{Colors.BLUE}⚙️  Resource Configuration{Colors.END}")
    config['CELERY_CONCURRENCY'] = prompt_input("Celery worker concurrency", default="4")
    
    return config

def write_env_file(config: Dict[str, str], filename: str = ".env.production"):
    """Write configuration to environment file"""
    env_content = f"""# VPK Production Environment Configuration
# Generated by setup.py on {subprocess.check_output(['date'], text=True).strip()}

# Domain Configuration
DOMAIN={config['DOMAIN']}
USE_SSL={config['USE_SSL']}
"""
    
    if config.get('ADMIN_EMAIL'):
        env_content += f"ADMIN_EMAIL={config['ADMIN_EMAIL']}\n"
    
    env_content += f"""
# Database Configuration
POSTGRES_USER={config['POSTGRES_USER']}
POSTGRES_PASSWORD={config['POSTGRES_PASSWORD']}
POSTGRES_DB={config['POSTGRES_DB']}

# Security Keys (KEEP THESE SECRET!)
SECRET_KEY='{config['SECRET_KEY']}'
SETTINGS_ENCRYPTION_KEY={config['SETTINGS_ENCRYPTION_KEY']}

# API Configuration
NEXT_PUBLIC_API_URL={config['NEXT_PUBLIC_API_URL']}

# Resource Configuration
CELERY_CONCURRENCY={config['CELERY_CONCURRENCY']}

# Production Settings
ENVIRONMENT=production
DEBUG=false
BACKEND_CORS_ORIGINS={config['BACKEND_CORS_ORIGINS']}
"""
    
    with open(filename, 'w') as f:
        f.write(env_content)
    
    # Set restrictive permissions
    os.chmod(filename, 0o600)
    
    print(f"{Colors.GREEN}✅ Environment file written to {filename}{Colors.END}")

def create_docker_override():
    """Create production docker-compose override"""
    override_content = """# Production Docker Compose Override
# This file customizes the base docker-compose.prod.yml for your specific environment

services:
  nginx:
    environment:
      - DOMAIN=${DOMAIN}
      - USE_SSL=${USE_SSL}
    volumes:
      - ./docker/nginx/templates:/etc/nginx/templates:ro
    
  celery_worker:
    environment:
      - CELERY_CONCURRENCY=${CELERY_CONCURRENCY}
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M
  
  backend:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
          
  frontend:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M
"""
    
    with open('docker-compose.override.yml', 'w') as f:
        f.write(override_content)
    
    print(f"{Colors.GREEN}✅ Docker Compose override created{Colors.END}")

def create_nginx_config(config: Dict[str, str]):
    """Create Nginx configuration"""
    # Create nginx directory structure
    nginx_dir = Path("docker/nginx/templates")
    nginx_dir.mkdir(parents=True, exist_ok=True)
    
    # Create main nginx template
    nginx_template = f"""
server {{
    listen 80;
    server_name {config['DOMAIN']};
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy strict-origin-when-cross-origin;
"""
    
    if config['USE_SSL'] == 'true':
        nginx_template += f"""
    # Redirect HTTP to HTTPS
    location / {{
        return 301 https://$server_name$request_uri;
    }}
}}

server {{
    listen 443 ssl;
    http2 on;
    server_name {config['DOMAIN']};
    
    # SSL Configuration (using manual certificates)
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy strict-origin-when-cross-origin;
"""
    
    nginx_template += """
    # File upload limits
    client_max_body_size 500M;
    
    # Frontend (Next.js)
    location / {
        proxy_pass http://frontend:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # API Backend
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
    
    # File uploads (special rate limiting)
    location /api/v1/storage/ {
        limit_req zone=upload burst=5 nodelay;
        
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Extended timeouts for file uploads
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
"""
    
    with open(nginx_dir / "default.conf.template", 'w') as f:
        f.write(nginx_template)
    
    print(f"{Colors.GREEN}✅ Nginx configuration created{Colors.END}")


def create_deployment_scripts(config: Dict[str, str]):
    """Create deployment and management scripts"""
    
    # Get the API URL from config
    api_url = config.get('NEXT_PUBLIC_API_URL', 'http://localhost')
    
    # Production deployment script
    deploy_script = f"""#!/bin/bash
# VPK Production Deployment Script

set -e

echo "🚀 Deploying VPK to production..."

# Check for environment file
if [ ! -f .env.production ]; then
    echo "❌ .env.production file not found. Run setup.py first."
    exit 1
fi

echo "✅ Found .env.production file"

# Build and start services with explicit env file
echo "📦 Building Docker images..."
sudo docker compose -f docker-compose.prod.yml --env-file .env.production build --no-cache

echo "🔄 Starting services..."
sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d

echo "⏳ Waiting for services to be ready..."
sleep 30

# Run database migrations
echo "🗄️  Running database migrations..."
sudo docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend alembic upgrade head

echo "✅ VPK deployment complete!"
echo "🌐 Access your VPK instance at: {api_url}"

# Show service status
sudo docker compose -f docker-compose.prod.yml --env-file .env.production ps
"""
    
    with open('deploy.sh', 'w') as f:
        f.write(deploy_script)
    os.chmod('deploy.sh', 0o755)
    
    # Management script
    manage_script = """#!/bin/bash
# VPK Management Script

set -e

COMMAND=${1:-help}

# Check for environment file
if [ ! -f .env.production ]; then
    echo "❌ .env.production file not found. Run setup.py first."
    exit 1
fi

case $COMMAND in
    start)
        echo "🚀 Starting VPK services..."
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d
        echo "✅ Services started"
        ;;
    stop)
        echo "🛑 Stopping VPK services..."
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production down
        echo "✅ Services stopped"
        ;;
    restart)
        echo "🔄 Restarting VPK services..."
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production restart
        echo "✅ Services restarted"
        ;;
    status)
        echo "📊 VPK Service Status:"
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production ps
        ;;
    logs)
        SERVICE=${2:-}
        if [ -n "$SERVICE" ]; then
            echo "📋 Logs for $SERVICE:"
            sudo docker compose -f docker-compose.prod.yml --env-file .env.production logs -f $SERVICE
        else
            echo "📋 All service logs:"
            sudo docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
        fi
        ;;
    update)
        echo "⬆️  Updating VPK..."
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production pull
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production build --no-cache
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d
        echo "✅ Update complete"
        ;;
    migrate)
        echo "🗄️  Running database migrations..."
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production exec backend alembic upgrade head
        echo "✅ Migrations complete"
        ;;
    shell)
        SERVICE=${2:-backend}
        echo "🐚 Opening shell in $SERVICE..."
        sudo docker compose -f docker-compose.prod.yml --env-file .env.production exec $SERVICE bash
        ;;
    help|*)
        echo "VPK Management Commands:"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Show service status"
        echo "  logs     - Show logs (optionally specify service)"
        echo "  update   - Update and restart services"
        echo "  migrate  - Run database migrations"
        echo "  shell    - Open shell in service (default: backend)"
        echo ""
        echo "Usage: ./manage.sh <command> [service]"
        ;;
esac
"""
    
    with open('manage.sh', 'w') as f:
        f.write(manage_script)
    os.chmod('manage.sh', 0o755)
    
    print(f"{Colors.GREEN}✅ Management scripts created (deploy.sh, manage.sh){Colors.END}")

def create_systemd_service():
    """Create systemd service for auto-start"""
    if not prompt_yes_no("Do you want to create a systemd service for auto-start?", default=False):
        return
    
    current_dir = os.getcwd()
    service_content = f"""[Unit]
Description=VPK (Vast Password Kracker) Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory={current_dir}
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml --env-file .env.production up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml --env-file .env.production down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
"""
    
    print(f"\n{Colors.YELLOW}To install the systemd service, run these commands as root:{Colors.END}")
    print(f"{Colors.CYAN}sudo tee /etc/systemd/system/vpk.service > /dev/null << 'EOF'")
    print(service_content)
    print("EOF")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable vpk.service")
    print(f"sudo systemctl start vpk.service{Colors.END}")

def main():
    """Main setup function"""
    print_banner()
    
    # Check prerequisites
    if not check_docker():
        print(f"\n{Colors.RED}❌ Docker is required but not installed.{Colors.END}")
        print(f"{Colors.YELLOW}Please install Docker and Docker Compose first:{Colors.END}")
        print(f"{Colors.CYAN}https://docs.docker.com/get-docker/{Colors.END}")
        sys.exit(1)
    
    # Check directory
    if not os.path.exists('docker-compose.prod.yml'):
        print(f"\n{Colors.RED}❌ Please run this script from the VPK root directory{Colors.END}")
        sys.exit(1)
    
    # Collect configuration
    config = collect_config()
    
    # Create configuration files
    print(f"\n{Colors.BOLD}{Colors.BLUE}📝 Creating configuration files...{Colors.END}")
    write_env_file(config)
    create_docker_override()
    create_nginx_config(config)
    create_deployment_scripts(config)
    
    # Create directories
    print(f"\n{Colors.BLUE}📁 Creating required directories...{Colors.END}")
    directories = [
        'app/data',
        'logs',
        'docker/certs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print(f"{Colors.GREEN}✅ Directories created{Colors.END}")
    
    # Create systemd service
    create_systemd_service()
    
    # Final instructions
    print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 VPK Production Setup Complete!{Colors.END}")
    print(f"\n{Colors.BOLD}Next steps:{Colors.END}")
    print(f"{Colors.WHITE}1. Review the generated configuration files{Colors.END}")
    print(f"{Colors.WHITE}2. Run the deployment: {Colors.CYAN}./deploy.sh{Colors.END}")
    
    if config['USE_SSL'] == 'true':
        print(f"{Colors.WHITE}3. Place SSL certificates in: {Colors.CYAN}docker/certs/{Colors.END}")
        print(f"   - {Colors.CYAN}fullchain.pem{Colors.END} (certificate chain)")
        print(f"   - {Colors.CYAN}privkey.pem{Colors.END} (private key)")
    
    print(f"{Colors.WHITE}4. Access VPK at: {Colors.CYAN}{config['NEXT_PUBLIC_API_URL']}{Colors.END}")
    
    print(f"\n{Colors.YELLOW}Management commands:{Colors.END}")
    print(f"{Colors.CYAN}./manage.sh start{Colors.END}    - Start services")
    print(f"{Colors.CYAN}./manage.sh stop{Colors.END}     - Stop services")
    print(f"{Colors.CYAN}./manage.sh status{Colors.END}   - Check status")
    print(f"{Colors.CYAN}./manage.sh logs{Colors.END}     - View logs")
    print(f"{Colors.CYAN}./manage.sh update{Colors.END}   - Update VPK")
    
    print(f"\n{Colors.YELLOW}Important files created:{Colors.END}")
    print(f"{Colors.CYAN}- .env.production{Colors.END} (environment variables)")
    print(f"{Colors.CYAN}- docker-compose.override.yml{Colors.END} (Docker overrides)")
    print(f"{Colors.CYAN}- deploy.sh{Colors.END} (deployment script)")
    print(f"{Colors.CYAN}- manage.sh{Colors.END} (management script)")
    
    print(f"\n{Colors.RED}⚠️  SECURITY REMINDER:{Colors.END}")
    print(f"{Colors.YELLOW}Keep your .env.production file secure - it contains sensitive keys!{Colors.END}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup cancelled by user.{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Setup failed: {e}{Colors.END}")
        sys.exit(1)