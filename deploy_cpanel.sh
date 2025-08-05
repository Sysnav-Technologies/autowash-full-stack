#!/bin/bash

# Django cPanel Deployment Script
# This script helps deploy Django to cPanel with proper static file handling

echo "🚀 Django cPanel Deployment Script"
echo "=================================="

# Set CPANEL environment variable
export CPANEL=True

# Create public_html directory structure if it doesn't exist
echo "📁 Creating directory structure..."
mkdir -p public_html/static
mkdir -p public_html/media

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Copy static files to public_html if different from STATIC_ROOT
if [ "$STATIC_ROOT" != "$(pwd)/public_html/static" ]; then
    echo "📋 Copying static files to public_html..."
    cp -r staticfiles/* public_html/static/ 2>/dev/null || :
fi

# Create/update .htaccess for proper MIME types
echo "⚙️ Creating .htaccess configuration..."
cat > public_html/.htaccess << 'EOF'
# Django cPanel .htaccess configuration

# Enable rewrite engine
RewriteEngine On

# Set proper MIME types for static files
<FilesMatch "\.(css)$">
    Header set Content-Type "text/css"
</FilesMatch>

<FilesMatch "\.(js)$">
    Header set Content-Type "application/javascript"
</FilesMatch>

<FilesMatch "\.(png|jpg|jpeg|gif|svg)$">
    Header set Content-Type "image/\1"
</FilesMatch>

<FilesMatch "\.(woff|woff2|ttf|eot)$">
    Header set Content-Type "font/\1"
</FilesMatch>

# Enable gzip compression
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/plain
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/xml
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE application/xhtml+xml
    AddOutputFilterByType DEFLATE application/rss+xml
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/x-javascript
</IfModule>

# Set cache headers for static files
<IfModule mod_expires.c>
    ExpiresActive on
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/jpg "access plus 1 year"
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
</IfModule>

# Serve static files directly without going through Django
RewriteCond %{REQUEST_URI} ^/static/
RewriteRule ^static/(.*)$ /static/$1 [L,QSA]

# Serve media files directly
RewriteCond %{REQUEST_URI} ^/media/
RewriteRule ^media/(.*)$ /media/$1 [L,QSA]

# Don't rewrite requests for existing files or directories
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d

# Pass all other requests to Django
RewriteRule ^(.*)$ /passenger_wsgi.py/$1 [QSA,L]
EOF

# Run migrations
echo "🗄️ Running migrations..."
python manage.py migrate --database=default

# Create cache table
echo "💾 Creating cache table..."
python manage.py createcachetable

echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Upload all files to your cPanel file manager"
echo "2. Make sure passenger_wsgi.py is in the root directory"
echo "3. Set Python version in cPanel to 3.8+"
echo "4. Add environment variables in cPanel"
echo "5. Restart the application"
echo ""
echo "🔧 If static files still don't work:"
echo "1. Check that mod_headers and mod_expires are enabled"
echo "2. Verify the static directory permissions (755)"
echo "3. Check cPanel error logs for any issues"
