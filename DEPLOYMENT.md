# VPK Production Deployment Guide

This guide helps you deploy VPK (Vast Password Kracker) in a production environment using Docker Compose.

## Prerequisites

- Linux server with Docker and Docker Compose installed
- Domain name pointed to your server (for production SSL)
- Ports 80 and 443 open in your firewall
- At least 4GB RAM and 20GB disk space
- Vast.ai API key ([Get one here](https://vast.ai/))
- AWS S3 bucket with access credentials

### AWS S3 Configuration

Create a dedicated user for the key and assign it an IAM policy. The policy will need read/write access. Alternatively, you can provide read-only access and it will be unable to upload but everything else will work fine:

```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOURBUCKETNAME/*",
        "arn:aws:s3:::YOURBUCKETNAME"
      ]
    }
  ]
}
```

## Production Deployment

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd VPK
```

### 2. Run Automated Setup
```bash
python setup.py
```

The setup wizard will:
- Verify Docker installation
- Collect configuration (domain, SSL, database settings)
- Generate secure encryption keys
- Create production configuration files
- Set up Nginx configuration with security headers
- Create deployment and management scripts

### 3. SSL Certificate Setup

Place your SSL certificates in:
```bash
docker/certs/fullchain.pem    # Certificate chain
docker/certs/privkey.pem      # Private key
```

Set `USE_SSL=true` in your environment configuration. Nginx will automatically redirect HTTP to HTTPS and enforce security headers.

### 4. Deploy Application
```bash
./deploy.sh
```

### 5. Service Management
```bash
./manage.sh status      # Check service status
./manage.sh logs        # View logs
./manage.sh stop        # Stop services
./manage.sh start       # Start services
./manage.sh restart     # Restart services
./manage.sh update      # Update VPK
./manage.sh migrate     # Run database migrations
```

## Development Setup

### 1. Clone and Configure
```bash
git clone <your-repo-url>
cd VPK
cp .env.example .env
```

### 2. Configure Environment Variables
Edit `.env` with your credentials:
```bash
# Vast.ai Configuration
VAST_API_KEY=your_vast_api_key

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
S3_REGION=us-east-1

# Security
SECRET_KEY=your_secret_key_here
SETTINGS_ENCRYPTION_KEY=your_encryption_fernet_key_here
```

### 3. Start Development Environment
```bash
docker-compose up -d
```

### 4. Initialise Database
```bash
docker-compose exec backend alembic upgrade head
```

### 5. Access Application
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Configuration Files Generated

The setup script creates the following files:

- `.env.production` - Environment variables and secrets
- `docker-compose.override.yml` - Production overrides with resource limits
- `docker/nginx/templates/default.conf.template` - Nginx configuration with security headers
- `deploy.sh` - Automated deployment script
- `manage.sh` - Service management script

### Key Configuration Features

- **Automatic Encryption Key Generation**: Secure SECRET_KEY and SETTINGS_ENCRYPTION_KEY
- **Domain Configuration**: Automatic CORS and API URL setup
- **Resource Limits**: Configurable Celery worker concurrency
- **Security Headers**: Nginx configuration with HSTS, XSS protection, and frame denial
- **Rate Limiting**: API endpoints protected with burst limits

## Environment Variables

### Required Variables in `.env.production`

**Domain & SSL Configuration:**
- `DOMAIN` - Your domain name (e.g., vpk.example.com)
- `USE_SSL` - Enable/disable SSL (true/false)
- `NEXT_PUBLIC_API_URL` - Frontend API URL (auto-configured)
- `BACKEND_CORS_ORIGINS` - CORS allowed origins (JSON array)

**Database Configuration:**
- `POSTGRES_USER` - PostgreSQL username
- `POSTGRES_PASSWORD` - PostgreSQL password
- `POSTGRES_DB` - Database name

**Security Keys:**
- `SECRET_KEY` - Application secret key (auto-generated)
- `SETTINGS_ENCRYPTION_KEY` - Fernet encryption key for settings

**Performance:**
- `CELERY_CONCURRENCY` - Worker process count (default: 4)

### Runtime Configuration (via Settings Page)

Most configuration is now managed through the web interface:

**API Keys:**
- Vast.ai API key
- AWS S3 credentials (Access Key ID, Secret Access Key)
- S3 bucket name and region

**Cost Management:**
- Maximum cost per hour
- Maximum total cost per job

**File Limits:**
- Maximum upload size (MB)
- Maximum hash file size (MB)
- Data retention period (days)

**Wordlist Catalogue:**
- Populate catalogue from Weakpass.com (admin feature)
- Enhanced wordlist metadata for accurate estimates

## First-Time Application Setup

After successful deployment:

1. **Create Admin User**: Register the first user through the web interface
2. **Configure Settings**: Go to Settings → Application Settings and configure:
   - Cost limits (max per hour, total cost)
   - File size limits and data retention
   - AWS S3 credentials and test connection
   - Vast.ai API key and test connection
3. **Populate Wordlist Catalogue**: Use Settings → Wordlist Catalogue Management
4. **Upload Resources**: Use Storage Management to upload:
   - Wordlists (supports .txt, .7z, .zip, .gz, .bz2 formats)
   - Rule files (.rule files)
5. **Test Job Creation**: Create a test job to verify full functionality

## Monitoring and Logs

View logs for specific services:
```bash
./manage.sh logs frontend
./manage.sh logs backend
./manage.sh logs celery_worker
./manage.sh logs nginx
```

## Troubleshooting

### Service Won't Start
1. Check logs: `./manage.sh logs <service>`
2. Verify configuration: `cat .env.production`
3. Check Docker status: `sudo docker compose -f docker-compose.prod.yml ps`
4. Ensure required directories exist: `app/data`, `logs`, `docker/certs`

### SSL Issues
1. Verify domain DNS points to your server
2. Check ports 80/443 are open
3. Ensure SSL certificates exist in `docker/certs/`:
   - `fullchain.pem` (certificate chain)
   - `privkey.pem` (private key)
4. Check Nginx logs: `./manage.sh logs nginx`

### Job Execution Issues
1. **Vast.ai Connection**: Check API key in Settings → Vast.ai Configuration
2. **AWS S3 Issues**: Verify credentials in Settings → AWS S3 Configuration
3. **Compressed Wordlists**: Ensure sufficient disk space for decompression
4. **Hash File Errors**: Verify hash format matches selected type

### Performance Issues
1. Monitor resources: `sudo docker stats`
2. Adjust Celery concurrency in `.env.production`
3. Check disk space for large compressed wordlists
4. Review job timeout settings

### Database Issues
1. Check database logs: `./manage.sh logs postgres`
2. Run migrations: `./manage.sh migrate`
3. Verify environment variables in `.env.production`
4. Check database health: `./manage.sh logs backend | grep -i database`

### Wordlist Catalogue Issues
1. Populate catalogue manually: Settings → Wordlist Catalogue Management
2. Check S3 connectivity for enhanced wordlist features
3. Verify wordlist naming conventions match catalogue entries

## Production Checklist

### Pre-Deployment
- [ ] Domain configured and DNS pointing to server
- [ ] Firewall configured (ports 80, 443 open)
- [ ] Docker and Docker Compose installed
- [ ] Vast.ai API key obtained
- [ ] AWS S3 bucket created with proper IAM permissions

### Deployment
- [ ] Setup script completed successfully (`python setup.py`)
- [ ] SSL certificates placed in `docker/certs/` (if using HTTPS)
- [ ] Initial deployment successful (`./deploy.sh`)
- [ ] Database migrations completed
- [ ] All services healthy (`./manage.sh status`)

### Configuration
- [ ] Application accessible via domain
- [ ] Admin user created and can log in
- [ ] Vast.ai API key configured and tested
- [ ] AWS S3 credentials configured and tested
- [ ] Cost limits set appropriately
- [ ] File size limits configured

### Testing
- [ ] Test wordlist upload (both regular and compressed formats)
- [ ] Test hash file upload
- [ ] Create and execute a simple test job
- [ ] Verify job logs and results download
- [ ] Test wordlist catalogue population (admin)
- [ ] Verify compressed wordlist handling (7z, zip, gz)

## Resource Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4GB (6GB+ recommended for heavy usage)
- **Disk**: 20GB base + space for logs
- **Network**: Stable internet for Vast.ai and S3 connectivity

### Scaling Considerations
- Increase `CELERY_CONCURRENCY` for more parallel job processing
- Monitor disk usage when handling large compressed wordlists
- Ensure adequate bandwidth for large wordlist downloads/uploads, also consider your egres costs on S3.

## Support

For issues and questions:
1. Check logs first: `./manage.sh logs`
2. Review this documentation and README.md
3. Test configuration using Settings page connection tests
4. Check GitHub issues
5. Create new issue with logs and configuration details
