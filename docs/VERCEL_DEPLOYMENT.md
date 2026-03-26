# Vercel Deployment Guide

This guide explains how to deploy the SyncLearn project to Vercel with Supabase database and Vercel Redis.

## Prerequisites

- Vercel account ([vercel.com](https://vercel.com))
- Supabase project ([supabase.com](https://supabase.com))
- AWS account with S3 bucket access
- GitHub repository connected to Vercel
- OpenAI API key

## Setup Steps

### 1. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Save the following credentials:
   - **Database URL**: Connection string in the format `postgresql://user:password@db.supabase.co:5432/postgres?sslmode=require`
   - **Project Reference**: Needed for API access

### 2. Create Vercel Redis Database

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Navigate to **Storage** → **Create Database** → **Redis**
3. Select **Vercel KV** (Redis store)
4. Create and get the connection string in the format `redis://:[password]@[host]:[port]`
5. Vercel will provide the `REDIS_URL` environment variable

### 3. Set Up AWS S3 Bucket

1. Go to [AWS Console](https://console.aws.amazon.com) and sign in
2. Navigate to **S3** and create a new bucket:
   - Bucket name: `synclearn-prod` (or your preferred name)
   - Region: Choose closest to your users (e.g., `us-east-1`)
   - Block Public Access: Keep enabled (we'll use presigned URLs)

3. **Create IAM User for S3 Access**:
   - Go to **IAM** → **Users** → **Create User**
   - Username: `synclearn-vercel`
   - Attach policy: `AmazonS3FullAccess` (or create custom policy)
   - Generate **Access Key ID** and **Secret Access Key**
   - Save these securely (you'll need them for Vercel env vars)

4. **Set CORS on S3 Bucket** (if serving presigned URLs to frontend):
   - Go to **S3** → Your bucket → **Permissions** → **CORS**
   - Add CORS configuration for your Vercel domain

### 4. Deploy to Vercel

1. **Connect Repository**: Connect your GitHub repository to Vercel
2. **Configure Environment Variables** in Vercel Project Settings:
   ```
   # Database
   DATABASE_URL = postgresql://user:password@db.supabase.co:5432/postgres?sslmode=require
   
   # Redis
   REDIS_URL = redis://:[password]@[host]:[port]
   
   # AWS S3
   AWS_ACCESS_KEY_ID = your-aws-access-key
   AWS_SECRET_ACCESS_KEY = your-aws-secret-key
   AWS_S3_BUCKET = your-s3-bucket-name
   AWS_S3_REGION = us-east-1
   
   # OpenAI
   OPENAI_API_KEY = your-openai-api-key
   
   # Application
   SECRET_KEY = your-secret-key
   FLASK_ENV = production
   FLASK_APP = backend/run.py
   ```

3. **Deploy**: Push to main branch or manually trigger deployment from Vercel dashboard

### 5. Database Migrations

After deployment, you may need to run Flask-Migrate to create database tables:

```bash
vercel env pull  # Pull environment variables locally
flask db upgrade # Run migrations
vercel deploy    # Redeploy
```

## Local Development Setup

### 1. Create .env File

Create `/backend/.env` with:

```env
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-dev-secret-key

# Supabase Database
DATABASE_URL=postgresql://user:password@db.supabase.co:5432/postgres?sslmode=require

# Vercel Redis (get from Vercel dashboard)
REDIS_URL=redis://:[password]@[host]:[port]

# AWS S3 (for local development, create a separate IAM user or use root credentials)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_S3_BUCKET=your-s3-bucket-name
AWS_S3_REGION=us-east-1

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=104857600
```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-dev-secret-key

# Supabase Database
DATABASE_URL=postgresql://user:password@db.supabase.co:5432/postgres?sslmode=require

# Vercel Redis (get from Vercel dashboard)
REDIS_URL=redis://:[password]@[host]:[port]

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=104857600
```

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt

cd ../frontend
npm install
```

### 3. Run Development Server

```bash
# Terminal 1: Backend
cd backend
python run.py

# Terminal 2: Frontend
cd frontend
npm start
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Vercel Platform                          │
├────────────────────────┬────────────────────────────────────┤
│  Frontend (React)      │      Backend (Flask API)           │
│  - React 18            │      - Flask 3.1.0                 │
│  - Axios HTTP Client   │      - REST API Endpoints          │
│  - React-Scripts Build │      - Celery Tasks                │
└──────────┬─────────────┬──────────────┬────────────────────┘
           │             │              │
    ┌──────▼──────┐  ┌────────▼─┐  ┌────────▼─────┐   ┌──────▼───┐
    │  Supabase   │  │Vercel   │  │   AWS S3     │   │ OpenAI   │
    │ PostgreSQL  │  │ Redis   │  │  File Storage│   │   API    │
    │  Database   │  │(Broker) │  │(Slides/Video)│   │          │
    └─────────────┘  └─────────┘  └──────────────┘   └──────────┘
```

## Key Configuration Files

- **`vercel.json`** - Vercel deployment configuration
- **`.vercelignore`** - Files to exclude from deployment
- **`backend/config.py`** - Flask application configuration with Supabase & Redis support
- **`backend/.env.example`** - Example environment variables
- **`backend/requirements.txt`** - Python dependencies

## Troubleshooting

### Database Connection Issues
- Ensure Supabase SSL mode is enabled in connection string
- Check that Supabase IP whitelist includes Vercel IPs
- Verify `sslmode=require` parameter in DATABASE_URL

### Redis Connection Issues
- Verify REDIS_URL format: `redis://:[password]@[host]:[port]`
- Check Vercel Redis database is created and active
- Ensure no connection timeout issues in Vercel logs

### Build Failures
- Check that all Python dependencies are in `requirements.txt`
- Verify Node.js dependencies in `frontend/package.json`
- Review Vercel build logs in dashboard

### S3 Connection Issues
- Verify AWS credentials are correct in environment variables
- Ensure S3 bucket name exists and is in the specified region
- Check that IAM user has `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` permissions
- For local development, test S3 access with: `aws s3 ls --profile your-profile`
- Verify AWS_S3_ENDPOINT_URL is only set for S3-compatible services (leave empty for AWS S3)

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Supabase PostgreSQL connection | `postgresql://...@db.supabase.co:5432/postgres?sslmode=require` |
| `REDIS_URL` | Vercel Redis connection | `redis://:[token]@[host]:[port]` |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key | (from AWS IAM console) |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key | (from AWS IAM console) |
| `AWS_S3_BUCKET` | S3 bucket name | `synclearn-prod` |
| `AWS_S3_REGION` | AWS region for S3 | `us-east-1` |
| `OPENAI_API_KEY` | OpenAI API authentication | (get from openai.com) |
| `SECRET_KEY` | Flask session encryption key | (generate random string) |
| `FLASK_ENV` | Environment mode | `production` |
| `TEMP_UPLOAD_DIR` | Temporary upload directory | `/tmp/synclearn_uploads` (Vercel: use /tmp) |

## Additional Resources

- [Vercel Documentation](https://vercel.com/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [The tech-stack.md](./tech-stack.md) for detailed technology list
