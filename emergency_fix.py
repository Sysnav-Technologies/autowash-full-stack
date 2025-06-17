#!/usr/bin/env python3
"""
Emergency Environment Fix for cPanel
Run this script to fix the CPANEL=active issue
Place this file in your project root and run: python emergency_fix.py
"""

import os
import sys
import subprocess
from pathlib import Path

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*50}")
    print(f"🚨 {title}")
    print(f"{'='*50}")

def print_section(title):
    """Print a section header"""
    print(f"\n🔍 {title}:")

def run_command(cmd):
    """Run a command and return the output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def main():
    print_header("EMERGENCY CPANEL ENVIRONMENT FIX")
    
    # Get current directory
    current_dir = Path.cwd()
    print(f"📍 Current directory: {current_dir}")
    
    # Step 1: Find all .env files
    print_section("SEARCHING FOR ALL .env FILES")
    
    # Search in current directory and parents
    env_files = []
    search_paths = [current_dir] + list(current_dir.parents)[:5]  # Limit to 5 parent dirs
    
    for path in search_paths:
        env_file = path / '.env'
        if env_file.exists():
            env_files.append(env_file)
            print(f"📄 Found: {env_file}")
            
            # Show problematic content
            try:
                with open(env_file, 'r') as f:
                    content = f.read()
                    lines = [line.strip() for line in content.splitlines() 
                            if any(var in line for var in ['CPANEL=', 'RENDER=', 'DEBUG='])]
                    if lines:
                        print(f"   Content preview:")
                        for line in lines[:5]:
                            print(f"   {line}")
            except Exception as e:
                print(f"   ❌ Error reading file: {e}")
    
    if not env_files:
        print("❌ No .env files found")
    
    # Step 2: Check current .env file specifically
    print_section("CHECKING CURRENT .env FILE")
    
    current_env = current_dir / '.env'
    if current_env.exists():
        print(f"📄 Found .env in current directory: {current_env}")
        
        try:
            with open(current_env, 'r') as f:
                content = f.read()
            
            print("   Full content:")
            for i, line in enumerate(content.splitlines()[:10], 1):
                print(f"   {i:2d}: {line}")
            
            # Check for problematic values
            problematic_found = False
            fixes_needed = []
            
            if 'CPANEL=active' in content:
                print("❌ Found CPANEL=active")
                fixes_needed.append(('CPANEL=active', 'CPANEL=True'))
                problematic_found = True
            
            if 'RENDER=active' in content:
                print("❌ Found RENDER=active")
                fixes_needed.append(('RENDER=active', 'RENDER=False'))
                problematic_found = True
            
            if 'DEBUG=active' in content:
                print("❌ Found DEBUG=active")  
                fixes_needed.append(('DEBUG=active', 'DEBUG=False'))
                problematic_found = True
            
            # Apply fixes
            if fixes_needed:
                print("\n🔧 APPLYING FIXES:")
                
                # Create backup
                backup_file = current_env.with_suffix('.env.emergency_backup')
                with open(backup_file, 'w') as f:
                    f.write(content)
                print(f"💾 Backup created: {backup_file}")
                
                # Apply fixes
                fixed_content = content
                for old_val, new_val in fixes_needed:
                    fixed_content = fixed_content.replace(old_val, new_val)
                    print(f"✅ Fixed: {old_val} → {new_val}")
                
                # Write fixed content
                with open(current_env, 'w') as f:
                    f.write(fixed_content)
                print("✅ Applied all fixes")
            
            if not problematic_found:
                print("✅ No problematic values found in current .env")
                
        except Exception as e:
            print(f"❌ Error processing .env file: {e}")
    else:
        print("❌ No .env file in current directory")
        print("📝 Creating new .env file...")
        
        # Create new .env file
        new_env_content = """CPANEL=True
RENDER=False
SECRET_KEY=your-super-secure-production-secret-key-here-make-it-very-long-and-random
DEBUG=False
ALLOWED_HOSTS=app.autowash.co.ke,autowash.co.ke,www.autowash.co.ke,*.autowash.co.ke

CPANEL_DOMAIN=app.autowash.co.ke
CPANEL_SUBDOMAIN=app

DATABASE_URL=postgresql://sysnav_user:wDQ0KpJJKE4auxScrXGJivT0AKIlBJW7@dpg-d13v9tu3jp1c73dg94r0-a.oregon-postgres.render.com/sysnav

EMAIL_HOST=mail.autowash.co.ke
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@autowash.co.ke
EMAIL_HOST_PASSWORD=your_email_password
DEFAULT_FROM_EMAIL=Autowash <noreply@autowash.co.ke>

MPESA_ENVIRONMENT=production
MPESA_CONSUMER_KEY=your_production_mpesa_consumer_key
MPESA_CONSUMER_SECRET=your_production_mpesa_consumer_secret
MPESA_SHORTCODE=your_production_shortcode
MPESA_PASSKEY=your_production_mpesa_passkey
MPESA_CALLBACK_URL=https://app.autowash.co.ke/api/mpesa/callback/
"""
        
        try:
            with open(current_env, 'w') as f:
                f.write(new_env_content)
            print("✅ Created new .env file")
        except Exception as e:
            print(f"❌ Error creating .env file: {e}")
    
    # Step 3: Test python-decouple
    print_section("TESTING PYTHON-DECOUPLE")
    
    try:
        # Add current directory to Python path
        sys.path.insert(0, str(current_dir))
        
        from decouple import config
        
        # Test raw values
        cpanel_raw = config('CPANEL', default='NOT_FOUND')
        render_raw = config('RENDER', default='NOT_FOUND')
        debug_raw = config('DEBUG', default='NOT_FOUND')
        
        print(f"   CPANEL raw value: {repr(cpanel_raw)}")
        print(f"   RENDER raw value: {repr(render_raw)}")
        print(f"   DEBUG raw value: {repr(debug_raw)}")
        
        # Test boolean casting
        try:
            cpanel_bool = config('CPANEL', default=False, cast=bool)
            print(f"   ✅ CPANEL as bool: {cpanel_bool}")
        except Exception as e:
            print(f"   ❌ CPANEL boolean error: {e}")
            
        try:
            render_bool = config('RENDER', default=False, cast=bool)
            print(f"   ✅ RENDER as bool: {render_bool}")
        except Exception as e:
            print(f"   ❌ RENDER boolean error: {e}")
            
        try:
            debug_bool = config('DEBUG', default=True, cast=bool)
            print(f"   ✅ DEBUG as bool: {debug_bool}")
        except Exception as e:
            print(f"   ❌ DEBUG boolean error: {e}")
            
    except ImportError:
        print("   ❌ python-decouple not installed")
    except Exception as e:
        print(f"   ❌ Error testing decouple: {e}")
    
    # Step 4: Check system environment variables
    print_section("CHECKING SYSTEM ENVIRONMENT VARIABLES")
    
    env_vars = ['CPANEL', 'RENDER', 'DEBUG', 'DJANGO_SETTINGS_MODULE']
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"   {var}={value} (from system environment)")
            if var in ['CPANEL', 'RENDER', 'DEBUG'] and value.lower() == 'active':
                print(f"   ⚠️ System environment variable {var} has problematic value!")
        else:
            print(f"   {var}=<not set>")
    
    # Step 5: Test Django settings loading
    print_section("TESTING DJANGO SETTINGS")
    
    # Try to test Django
    try:
        returncode, stdout, stderr = run_command("python manage.py check")
        
        if returncode == 0:
            print("   ✅ Django check passed!")
            print("   Output:", stdout[:200] + "..." if len(stdout) > 200 else stdout)
        else:
            print("   ❌ Django check failed")
            print("   Error:", stderr[:500] + "..." if len(stderr) > 500 else stderr)
            
            # If it's still the same error, show more specific help
            if 'Invalid truth value: active' in stderr:
                print("\n   🚨 STILL GETTING THE SAME ERROR!")
                print("   This suggests there might be:")
                print("   1. Another .env file in a parent directory")
                print("   2. System environment variables set by cPanel")
                print("   3. Cached Python bytecode")
                
                # Try to clear Python cache
                print("   🧹 Clearing Python cache...")
                try:
                    # Remove __pycache__ directories
                    for root, dirs, files in os.walk(current_dir):
                        if '__pycache__' in dirs:
                            cache_dir = Path(root) / '__pycache__'
                            try:
                                import shutil
                                shutil.rmtree(cache_dir)
                                print(f"   Removed: {cache_dir}")
                            except:
                                pass
                except:
                    pass
                
    except Exception as e:
        print(f"   ❌ Error running Django check: {e}")
    
    # Step 6: Final recommendations
    print_section("FINAL RECOMMENDATIONS")
    
    print("   1. ✅ If Django check passed:")
    print("      Run: python manage.py deploy --environment cpanel")
    print("")
    print("   2. ❌ If still getting 'Invalid truth value: active':")
    print("      a) Check if cPanel has set environment variables")
    print("      b) Look for .env files in parent directories")
    print("      c) Contact cPanel support about environment variables")
    print("")
    print("   3. 🔧 Manual override option:")
    print("      Edit settings.py and replace:")
    print("      CPANEL = config('CPANEL', default=False, cast=bool)")
    print("      with:")
    print("      CPANEL = True  # Hardcoded for cPanel")
    print("")
    print("   4. 📧 Alternative:")
    print("      Set DJANGO_SETTINGS_MODULE to use a different settings file")
    
    print(f"\n{'='*50}")
    print("✅ Emergency fix script completed!")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()