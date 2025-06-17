"""
Debug Environment Management Command
Place this in: apps/core/management/commands/debug_env.py
"""

import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Debug environment configuration issues for cPanel/Render/Local deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to automatically fix common issues'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show verbose output'
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS('🔍 DEBUGGING ENVIRONMENT CONFIGURATION'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        try:
            # Step 1: Check current directory and project structure
            self.check_project_structure()
            
            # Step 2: Find all .env files
            self.find_env_files()
            
            # Step 3: Analyze .env file content
            self.analyze_env_content()
            
            # Step 4: Test decouple loading
            self.test_decouple_loading()
            
            # Step 5: Check Django settings loading
            self.test_django_settings()
            
            # Step 6: Check for hidden characters
            self.check_hidden_characters()
            
            # Step 7: Environment variable conflicts
            self.check_env_variables()
            
            # Step 8: Auto-fix if requested
            if options['fix']:
                self.auto_fix_issues()
            
            # Step 9: Summary and recommendations
            self.show_recommendations()
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Debug failed: {str(e)}')
            )
            import traceback
            if self.verbose:
                self.stdout.write(self.style.ERROR(traceback.format_exc()))

    def check_project_structure(self):
        """Check project directory structure"""
        self.stdout.write('\n📁 PROJECT STRUCTURE:')
        
        current_dir = Path.cwd()
        base_dir = getattr(settings, 'BASE_DIR', current_dir)
        
        self.stdout.write(f'   Current directory: {current_dir}')
        self.stdout.write(f'   Django BASE_DIR: {base_dir}')
        self.stdout.write(f'   Python executable: {sys.executable}')
        self.stdout.write(f'   Python version: {sys.version.split()[0]}')
        
        # Check if manage.py exists
        manage_py = current_dir / 'manage.py'
        if manage_py.exists():
            self.stdout.write('   ✅ manage.py found')
        else:
            self.stdout.write('   ❌ manage.py not found')
        
        # Check settings module
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')
        self.stdout.write(f'   DJANGO_SETTINGS_MODULE: {settings_module}')

    def find_env_files(self):
        """Find all .env files in the project"""
        self.stdout.write('\n🔍 SEARCHING FOR .env FILES:')
        
        current_dir = Path.cwd()
        env_files = []
        
        # Search in current directory and parents
        search_paths = [current_dir] + list(current_dir.parents)
        
        for path in search_paths[:5]:  # Limit search to 5 parent directories
            env_file = path / '.env'
            if env_file.exists():
                env_files.append(env_file)
                self.stdout.write(f'   📄 Found: {env_file}')
        
        # Also search in common locations
        common_paths = [
            Path.home() / '.env',
            Path('/home1/autowash') / '.env',
            Path('/home1/autowash/app') / '.env',
            Path('/home1/autowash/main') / '.env',
        ]
        
        for path in common_paths:
            if path.exists() and path not in env_files:
                env_files.append(path)
                self.stdout.write(f'   📄 Found: {path}')
        
        if not env_files:
            self.stdout.write('   ❌ No .env files found')
        
        self.env_files = env_files

    def analyze_env_content(self):
        """Analyze .env file content"""
        self.stdout.write('\n📋 ANALYZING .env FILE CONTENT:')
        
        if not hasattr(self, 'env_files') or not self.env_files:
            self.stdout.write('   ❌ No .env files to analyze')
            return
        
        for env_file in self.env_files:
            self.stdout.write(f'\n   📄 File: {env_file}')
            
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for key environment variables
                key_vars = ['CPANEL', 'RENDER', 'DEBUG', 'SECRET_KEY']
                
                for var in key_vars:
                    lines = [line.strip() for line in content.splitlines() 
                            if line.strip().startswith(f'{var}=')]
                    
                    if lines:
                        for line in lines:
                            self.stdout.write(f'      {line}')
                            
                            # Check for problematic values
                            if var in ['CPANEL', 'RENDER', 'DEBUG']:
                                value = line.split('=', 1)[1] if '=' in line else ''
                                if value.lower() in ['active', 'inactive', 'on', 'off']:
                                    self.stdout.write(
                                        self.style.WARNING(f'      ⚠️  Problematic boolean value: {value}')
                                    )
                    else:
                        self.stdout.write(f'      {var}=<not found>')
                
            except Exception as e:
                self.stdout.write(f'      ❌ Error reading file: {e}')

    def test_decouple_loading(self):
        """Test python-decouple loading"""
        self.stdout.write('\n🔧 TESTING PYTHON-DECOUPLE LOADING:')
        
        try:
            from decouple import config, Csv, RepositoryEnv
            
            # Test loading key variables
            test_vars = {
                'CPANEL': (False, bool),
                'RENDER': (False, bool),
                'DEBUG': (True, bool),
                'SECRET_KEY': ('default-key', str),
            }
            
            for var_name, (default, cast_type) in test_vars.items():
                try:
                    if cast_type == bool:
                        value = config(var_name, default=default, cast=bool)
                        raw_value = config(var_name, default='NOT_FOUND')
                        self.stdout.write(f'   {var_name}: {value} (raw: "{raw_value}")')
                    else:
                        value = config(var_name, default=default, cast=cast_type)
                        self.stdout.write(f'   {var_name}: {value[:20]}...' if len(str(value)) > 20 else f'   {var_name}: {value}')
                        
                except Exception as e:
                    self.stdout.write(f'   ❌ {var_name}: Error - {e}')
            
            # Test which .env file is being used
            try:
                from decouple import AutoConfig
                config_obj = AutoConfig()
                if hasattr(config_obj, 'config'):
                    self.stdout.write(f'   📍 Decouple config source: {type(config_obj.config)}')
            except:
                pass
                
        except ImportError:
            self.stdout.write('   ❌ python-decouple not installed')
        except Exception as e:
            self.stdout.write(f'   ❌ Error testing decouple: {e}')

    def test_django_settings(self):
        """Test Django settings loading"""
        self.stdout.write('\n⚙️ TESTING DJANGO SETTINGS:')
        
        try:
            # Test environment detection
            render = getattr(settings, 'RENDER', 'NOT_SET')
            cpanel = getattr(settings, 'CPANEL', 'NOT_SET')
            debug = getattr(settings, 'DEBUG', 'NOT_SET')
            
            self.stdout.write(f'   RENDER setting: {render}')
            self.stdout.write(f'   CPANEL setting: {cpanel}')
            self.stdout.write(f'   DEBUG setting: {debug}')
            
            # Detect environment
            if cpanel:
                environment = 'cPanel'
            elif render:
                environment = 'Render'
            else:
                environment = 'Local'
            
            self.stdout.write(f'   🎯 Detected environment: {environment}')
            
            # Test database configuration
            db_engine = settings.DATABASES['default']['ENGINE']
            self.stdout.write(f'   🗄️ Database engine: {db_engine}')
            
            if 'django_tenants' in db_engine:
                self.stdout.write('   ✅ Django-tenants configured')
            else:
                self.stdout.write('   ⚠️ Django-tenants NOT configured')
                
        except Exception as e:
            self.stdout.write(f'   ❌ Error accessing Django settings: {e}')

    def check_hidden_characters(self):
        """Check for hidden characters in .env files"""
        self.stdout.write('\n🔍 CHECKING FOR HIDDEN CHARACTERS:')
        
        if not hasattr(self, 'env_files') or not self.env_files:
            return
        
        for env_file in self.env_files:
            self.stdout.write(f'\n   📄 File: {env_file}')
            
            try:
                with open(env_file, 'rb') as f:
                    content = f.read()
                
                # Check for BOM
                if content.startswith(b'\xef\xbb\xbf'):
                    self.stdout.write('   ⚠️ UTF-8 BOM detected')
                
                # Check for Windows line endings
                if b'\r\n' in content:
                    self.stdout.write('   ⚠️ Windows line endings (\\r\\n) detected')
                
                # Check CPANEL line specifically
                lines = content.decode('utf-8', errors='ignore').splitlines()
                for i, line in enumerate(lines, 1):
                    if line.startswith('CPANEL='):
                        # Show hex representation
                        line_bytes = line.encode('utf-8')
                        hex_repr = ' '.join(f'{b:02x}' for b in line_bytes)
                        self.stdout.write(f'   Line {i} hex: {hex_repr}')
                        
                        # Check for trailing spaces
                        if line.endswith(' ') or line.endswith('\t'):
                            self.stdout.write('   ⚠️ Trailing whitespace detected')
                        break
                        
            except Exception as e:
                self.stdout.write(f'   ❌ Error checking file: {e}')

    def check_env_variables(self):
        """Check for conflicting environment variables"""
        self.stdout.write('\n🌍 CHECKING ENVIRONMENT VARIABLES:')
        
        # Check system environment variables
        env_vars = ['CPANEL', 'RENDER', 'DEBUG', 'DJANGO_SETTINGS_MODULE']
        
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                self.stdout.write(f'   {var}={value} (from system environment)')
            else:
                self.stdout.write(f'   {var}=<not set>')
        
        # Check for cPanel-specific environment variables
        cpanel_vars = [var for var in os.environ.keys() if 'CPANEL' in var.upper()]
        if cpanel_vars:
            self.stdout.write(f'   🏢 cPanel-related env vars: {", ".join(cpanel_vars)}')

    def auto_fix_issues(self):
        """Attempt to automatically fix common issues"""
        self.stdout.write('\n🔧 ATTEMPTING AUTO-FIX:')
        
        if not hasattr(self, 'env_files') or not self.env_files:
            self.stdout.write('   ❌ No .env files found to fix')
            return
        
        for env_file in self.env_files:
            self.stdout.write(f'\n   📄 Fixing: {env_file}')
            
            try:
                # Read current content
                with open(env_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Remove BOM if present
                content = content.encode('utf-8').decode('utf-8-sig')
                
                # Fix line endings
                content = content.replace('\r\n', '\n').replace('\r', '\n')
                
                # Fix problematic boolean values
                fixes = [
                    ('CPANEL=active', 'CPANEL=True'),
                    ('CPANEL=inactive', 'CPANEL=False'),
                    ('RENDER=active', 'RENDER=True'),
                    ('RENDER=inactive', 'RENDER=False'),
                    ('DEBUG=on', 'DEBUG=True'),
                    ('DEBUG=off', 'DEBUG=False'),
                ]
                
                fixed_count = 0
                for old, new in fixes:
                    if old in content:
                        content = content.replace(old, new)
                        fixed_count += 1
                        self.stdout.write(f'      ✅ Fixed: {old} → {new}')
                
                # Remove trailing whitespace from lines
                lines = []
                for line in content.splitlines():
                    lines.append(line.rstrip())
                content = '\n'.join(lines)
                
                if fixed_count > 0:
                    # Create backup
                    backup_file = env_file.with_suffix('.env.backup')
                    env_file.rename(backup_file)
                    self.stdout.write(f'      💾 Backup created: {backup_file}')
                    
                    # Write fixed content
                    with open(env_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    self.stdout.write(f'      ✅ Fixed {fixed_count} issues')
                else:
                    self.stdout.write('      ✅ No issues found to fix')
                    
            except Exception as e:
                self.stdout.write(f'      ❌ Error fixing file: {e}')

    def show_recommendations(self):
        """Show recommendations based on findings"""
        self.stdout.write('\n💡 RECOMMENDATIONS:')
        
        self.stdout.write('\n   1. If you see "Invalid truth value: active":')
        self.stdout.write('      Run: python manage.py debug_env --fix')
        
        self.stdout.write('\n   2. If multiple .env files exist:')
        self.stdout.write('      Keep only the one in your project root')
        
        self.stdout.write('\n   3. Valid boolean values for .env:')
        self.stdout.write('      True/False, 1/0, yes/no, on/off')
        
        self.stdout.write('\n   4. After fixing, test with:')
        self.stdout.write('      python manage.py check')
        
        self.stdout.write('\n   5. If issues persist:')
        self.stdout.write('      python manage.py debug_env --verbose')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Debug complete!'))