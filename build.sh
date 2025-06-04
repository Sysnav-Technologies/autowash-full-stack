# Save as: build.sh (make executable: chmod +x build.sh)
#!/usr/bin/env bash

set -o errexit

echo "🚀 Autowash Render Deployment Starting..."

# Install dependencies
pip install -r requirements.txt

# Use your existing deploy command
python manage.py deploy

echo "✅ Autowash deployed successfully!"