#!/usr/bin/env python3
"""
cPanel Django 404 Diagnostic Script
Run this to diagnose why you're getting 404 errors
"""

import os
import sys
from pathlib import Path

def print_header(title):
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print(f"{'='*50}")

def print_section(title):
    print(f"\n📋 {title}:")

def main():
    print_header("CPANEL DJANGO 404 DIAGNOSTIC")
    
    current_dir = Path.cwd()
    print(f"📍 Current directory: {current_dir}")
    
    # Check 1: Verify files exist
    print_section("CHECKING REQUIRED FILES")
    
    required_files = [
        'manage.py',
        'passenger_wsgi.py',
        '.htaccess',
        'autowash/settings.py',
        'autowash/urls.py',
        'autowash/wsgi.py'
    ]
    
    for file_path in required_files:
        file = current_dir / file_path
        if file.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING!")
    
    # Check 2: Test Django import
    print_section("TESTING DJANGO IMPORT")
    
    try:
        sys.path.insert(0, str(current_dir))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
        
        from django.core.wsgi import get_wsgi_application
        from django.conf import settings
        
        app = get_wsgi_application()
        print("   ✅ Django imports successfully")
        print(f"   ✅ Debug mode: {settings.DEBUG}")
        print(f"   ✅ Allowed hosts: {settings.ALLOWED_HOSTS}")
        
        # Check URL configuration
        try:
            from django.urls import reverse
            from autowash.urls import urlpatterns
            print(f"   ✅ URL patterns loaded: {len(urlpatterns)} patterns")
            
            # Try to reverse some common URLs
            try:
                admin_url = reverse('admin:index')
                print(f"   ✅ Admin URL works: {admin_url}")
            except:
                print("   ⚠️ Admin URL might not be configured")
                
        except Exception as e:
            print(f"   ⚠️ URL configuration issue: {e}")
        
    except Exception as e:
        print(f"   ❌ Django import failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Check 3: Test passenger_wsgi.py
    print_section("TESTING PASSENGER_WSGI.PY")
    
    passenger_wsgi = current_dir / 'passenger_wsgi.py'
    if passenger_wsgi.exists():
        try:
            with open(passenger_wsgi, 'r') as f:
                content = f.read()
            
            if 'django.core.wsgi' in content:
                print("   ✅ passenger_wsgi.py has Django imports")
            else:
                print("   ❌ passenger_wsgi.py missing Django imports")
                
            if 'autowash.settings' in content:
                print("   ✅ passenger_wsgi.py has correct settings module")
            else:
                print("   ❌ passenger_wsgi.py missing settings module")
                
            # Check file permissions
            import stat
            perms = oct(os.stat(passenger_wsgi)[stat.ST_MODE])[-3:]
            print(f"   📁 File permissions: {perms}")
            if perms == '755':
                print("   ✅ Permissions are correct")
            else:
                print("   ⚠️ Permissions should be 755")
                
        except Exception as e:
            print(f"   ❌ Error reading passenger_wsgi.py: {e}")
    else:
        print("   ❌ passenger_wsgi.py not found")
    
    # Check 4: Verify directory structure
    print_section("CHECKING DIRECTORY STRUCTURE")
    
    expected_dirs = [
        'autowash',
        'apps',
        'templates',
        'static',
        'logs'
    ]
    
    for dir_name in expected_dirs:
        dir_path = current_dir / dir_name
        if dir_path.exists():
            print(f"   ✅ {dir_name}/")
            if dir_name == 'autowash':
                # Check autowash subdirectory
                autowash_files = ['settings.py', 'urls.py', 'wsgi.py', '__init__.py']
                for autowash_file in autowash_files:
                    file_path = dir_path / autowash_file
                    if file_path.exists():
                        print(f"      ✅ {autowash_file}")
                    else:
                        print(f"      ❌ {autowash_file} - MISSING!")
        else:
            if dir_name == 'static':
                print(f"   ⚠️ {dir_name}/ - Missing (might cause static file issues)")
            else:
                print(f"   ❌ {dir_name}/ - MISSING!")
    
    # Check 5: Test simple Django check
    print_section("RUNNING DJANGO CHECK")
    
    try:
        import subprocess
        result = subprocess.run([sys.executable, 'manage.py', 'check'], 
                              capture_output=True, text=True, cwd=current_dir)
        
        if result.returncode == 0:
            print("   ✅ Django check passed")
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
        else:
            print("   ❌ Django check failed")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
                
    except Exception as e:
        print(f"   ❌ Could not run Django check: {e}")
    
    # Check 6: Suggest creating a test view
    print_section("CREATING TEST VIEW")
    
    try:
        # Create a simple test view file
        test_view_content = '''from django.http import HttpResponse
from django.shortcuts import render

def test_view(request):
    return HttpResponse("""
    <html>
    <head><title>Django Test</title></head>
    <body>
        <h1>✅ Django is Working!</h1>
        <p>This confirms that Django is properly configured.</p>
        <p>Time: {}</p>
        <hr>
        <p><a href="/admin/">Admin Panel</a></p>
    </body>
    </html>
    """.format(request.META.get('HTTP_HOST', 'Unknown')))
'''
        
        test_views_file = current_dir / 'test_views.py'
        with open(test_views_file, 'w') as f:
            f.write(test_view_content)
        
        print(f"   ✅ Created test view file: {test_views_file}")
        print("   📝 Add this to your main urls.py:")
        print("       from test_views import test_view")
        print("       urlpatterns += [path('test/', test_view, name='test')]")
        
    except Exception as e:
        print(f"   ❌ Could not create test view: {e}")
    
    # Check 7: Environment variables
    print_section("ENVIRONMENT VARIABLES")
    
    important_env_vars = [
        'DJANGO_SETTINGS_MODULE',
        'PYTHONPATH',
        'PATH'
    ]
    
    for var in important_env_vars:
        value = os.environ.get(var, 'Not set')
        print(f"   {var}: {value}")
    
    # Final recommendations
    print_section("RECOMMENDATIONS")
    
    print("   🎯 Next steps to fix 404:")
    print("")
    print("   1. 📋 Check your main urls.py file:")
    print("      - Ensure it has URL patterns")
    print("      - Add a root URL pattern: path('', your_view)")
    print("")
    print("   2. 🌐 Test specific URLs:")
    print("      - https://app.autowash.co.ke/admin/")
    print("      - https://app.autowash.co.ke/test/ (if you add the test view)")
    print("")
    print("   3. 📁 Check your ROOT_URLCONF setting:")
    print("      - Should be 'autowash.urls' in settings.py")
    print("")
    print("   4. 🔄 Restart the application:")
    print("      - touch passenger_wsgi.py")
    print("")
    print("   5. 📝 Check cPanel Error Logs for specific errors")
    
    print_header("DIAGNOSTIC COMPLETE")

if __name__ == "__main__":
    main()