#!/usr/bin/env python3
"""
Fix OpenBLAS/NumPy issues for cPanel
Run this script to fix the threading issues
"""

import os
from pathlib import Path

def fix_openblas_issues():
    print("🔧 FIXING OPENBLAS/NUMPY ISSUES")
    print("=" * 40)
    
    current_dir = Path.cwd()
    
    # 1. Create .htaccess with OpenBLAS fix
    htaccess_content = '''# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION BEGIN
PassengerAppRoot "/home1/autowash/app.autowash.co.ke/app"
PassengerBaseURI "/"
PassengerPython "/home1/autowash/virtualenv/app.autowash.co.ke/app/3.13/bin/python"

# Fix OpenBLAS thread limit issue
PassengerAppEnv OPENBLAS_NUM_THREADS 1

# Additional Django-specific configurations
PassengerStartupFile passenger_wsgi.py
PassengerAppType wsgi
PassengerRestartDir "/home1/autowash/app.autowash.co.ke/app"

# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION END

# Django static files handling
<IfModule mod_rewrite.c>
    RewriteEngine On
    
    # Serve static files directly
    RewriteRule ^static/(.*)$ /static/$1 [L]
    RewriteRule ^media/(.*)$ /media/$1 [L]
    
    # Handle favicon
    RewriteRule ^favicon\.ico$ /static/favicon.ico [L]
    
    # Pass everything else to Django
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^(.*)$ /passenger_wsgi.py/$1 [QSA,L]
</IfModule>

# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION BEGIN
<IfModule Litespeed>
</IfModule>
# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION END'''
    
    htaccess_file = current_dir / '.htaccess'
    try:
        with open(htaccess_file, 'w') as f:
            f.write(htaccess_content)
        print("✅ Created .htaccess with OpenBLAS fix")
    except Exception as e:
        print(f"❌ Error creating .htaccess: {e}")
    
    # 2. Update passenger_wsgi.py with environment variables
    passenger_wsgi = current_dir / 'passenger_wsgi.py'
    
    if passenger_wsgi.exists():
        # Add OpenBLAS environment variables to passenger_wsgi.py
        env_fix = '''#!/usr/bin/python3
# Fix OpenBLAS threading issues for cPanel
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

import sys
from pathlib import Path

# Add project directory to Python path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as e:
    # Error handling for cPanel
    def application(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/html')]
        start_response(status, headers)
        error_html = f"""<html>
<head><title>Django Error</title></head>
<body>
<h1>Django Application Error</h1>
<p>Error: {str(e)}</p>
<p>Please check the logs for more details.</p>
</body>
</html>"""
        return [error_html.encode('utf-8')]
'''
        
        try:
            with open(passenger_wsgi, 'w') as f:
                f.write(env_fix)
            os.chmod(passenger_wsgi, 0o755)
            print("✅ Updated passenger_wsgi.py with OpenBLAS fix")
        except Exception as e:
            print(f"❌ Error updating passenger_wsgi.py: {e}")
    
    # 3. Create static directory
    static_dir = current_dir / 'static'
    if not static_dir.exists():
        try:
            static_dir.mkdir(parents=True, exist_ok=True)
            
            # Create basic subdirectories
            (static_dir / 'css').mkdir(exist_ok=True)
            (static_dir / 'js').mkdir(exist_ok=True)
            (static_dir / 'images').mkdir(exist_ok=True)
            
            # Create a basic favicon
            favicon_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="#007bff"/>
  <text x="16" y="20" text-anchor="middle" fill="white" font-family="Arial" font-size="18" font-weight="bold">A</text>
</svg>'''
            with open(static_dir / 'favicon.ico', 'w') as f:
                f.write(favicon_content)
            
            print("✅ Created static directory with subdirectories")
        except Exception as e:
            print(f"❌ Error creating static directory: {e}")
    
    # 4. Create a simple test view that bypasses admin autodiscovery
    test_urls_content = '''from django.http import HttpResponse
from django.urls import path

def simple_test(request):
    return HttpResponse("""
    <html>
    <head><title>Django Test - Working!</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1 style="color: green;">✅ Django is Working!</h1>
        <p>This confirms Django is properly running on cPanel.</p>
        <p><strong>Server:</strong> cPanel Passenger</p>
        <p><strong>Path:</strong> {}</p>
        <hr>
        <p><a href="/admin/">Try Admin Panel</a></p>
    </body>
    </html>
    """.format(request.path))

# Simple URL pattern for testing
urlpatterns = [
    path('test/', simple_test, name='simple_test'),
    path('', simple_test, name='home'),  # Root URL
]
'''
    
    test_urls_file = current_dir / 'test_urls.py'
    try:
        with open(test_urls_file, 'w') as f:
            f.write(test_urls_content)
        print("✅ Created test_urls.py for simple testing")
        print("   💡 Add 'include(\"test_urls\")' to your main urls.py for testing")
    except Exception as e:
        print(f"❌ Error creating test URLs: {e}")
    
    # 5. Restart the application
    try:
        os.utime(passenger_wsgi, None)
        print("✅ Restarted application (touched passenger_wsgi.py)")
    except Exception as e:
        print(f"❌ Error restarting: {e}")
    
    print("\n🎯 NEXT STEPS:")
    print("1. Test the root URL: https://app.autowash.co.ke/")
    print("2. Test the test URL: https://app.autowash.co.ke/test/")
    print("3. If working, gradually enable other features")
    print("4. Check cPanel Error Logs for any remaining issues")
    
    print("\n✅ OpenBLAS/NumPy fix applied!")

if __name__ == "__main__":
    fix_openblas_issues()