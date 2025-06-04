#!/usr/bin/env bash

set -o errexit

echo "🚀 Autowash Render Deployment Starting..."

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files BEFORE running deploy command
echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

# Use your existing deploy command (but skip static collection since we just did it)
echo "🔧 Running deployment setup..."
python manage.py deploy --skip-static

echo "✅ Autowash deployed successfully!"