#!/usr/bin/env bash

set -o errexit

echo "🚀 Autowash Render Deployment Starting..."

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

echo "🔧 Running deployment setup..."
python manage.py deploy 

echo "✅ Autowash deployed successfully!"