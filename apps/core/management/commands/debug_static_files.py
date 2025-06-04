# Add this to a management command or run in Django shell to debug
import os
from django.conf import settings
from django.contrib.staticfiles import finders

def debug_static_files():
    print("=== STATIC FILES DEBUG ===")
    print(f"DEBUG: {settings.DEBUG}")
    print(f"STATIC_URL: {settings.STATIC_URL}")
    print(f"STATIC_ROOT: {getattr(settings, 'STATIC_ROOT', 'NOT SET')}")
    print(f"STATICFILES_DIRS: {getattr(settings, 'STATICFILES_DIRS', 'NOT SET')}")
    
    # Check if static root exists and has files
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root and os.path.exists(static_root):
        print(f"\nSTATIC_ROOT directory exists: {static_root}")
        print("Contents:")
        for root, dirs, files in os.walk(static_root):
            level = root.replace(static_root, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files[:10]:  # Show first 10 files
                print(f"{subindent}{file}")
    else:
        print(f"\nSTATIC_ROOT doesn't exist: {static_root}")
    
    # Check specific files
    files_to_check = [
        'css/custom.css',
        'css/public.css', 
        'js/common.js',
        'js/public.js',
        'img/dashboard-preview.png'
    ]
    
    print("\n=== CHECKING SPECIFIC FILES ===")
    for file_path in files_to_check:
        found = finders.find(file_path)
        print(f"{file_path}: {'FOUND' if found else 'NOT FOUND'} {found or ''}")

# Run this function to debug
debug_static_files()