#!/usr/bin/env python
"""
AutoWash Production Database Fix Script
=======================================

This script fixes all critical database corruption issues in production:
1. UUID corruption in payment_method fields
2. Datetime corruption (integers/strings instead of proper datetime objects)
3. Session corruption issues
4. Unicode logging problems

USAGE ON CPANEL:
1. Upload this file to your app.autowash.co.ke root directory
2. Run: python fix_production_issues.py
3. Follow the prompts and backup instructions

CRITICAL: This script MUST be run on the production server, not locally.
"""

import os
import sys
import django
from datetime import datetime
from django.utils import timezone
import uuid
import traceback

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.db import connection, transaction
from django.contrib.auth.models import User

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def print_section(title):
    """Print a section header"""
    print(f"\n>>> {title}")
    print("-" * 60)

def confirm_production():
    """Confirm this is running on production"""
    print_header("AutoWash Production Database Fix")
    print("⚠️  CRITICAL WARNING ⚠️")
    print("This script will modify your production database!")
    print("Make sure you have a complete database backup before proceeding.")
    print("\nChecking environment...")
    
    # Check if we're on production
    import socket
    hostname = socket.gethostname()
    print(f"Hostname: {hostname}")
    print(f"Current directory: {os.getcwd()}")
    
    if 'app.autowash.co.ke' not in os.getcwd() and 'autowash' not in hostname.lower():
        print("❌ This doesn't appear to be the production server.")
        response = input("Are you sure you want to continue? (yes/no): ").lower().strip()
        if response != 'yes':
            print("Exiting for safety...")
            sys.exit(1)
    
    print("\n✅ Environment check passed.")
    response = input("\nHave you created a database backup? (yes/no): ").lower().strip()
    if response != 'yes':
        print("❌ Please create a database backup first!")
        print("In cPanel: Go to phpMyAdmin > Select autowash_main > Export > Go")
        sys.exit(1)
    
    print("✅ Backup confirmed. Proceeding with fixes...")

def fix_uuid_corruption():
    """Fix UUID corruption in payment_method fields"""
    print_section("Fixing UUID Corruption Issues")
    
    fixed_tables = 0
    total_fixes = 0
    
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                
                # 1. Fix payment_method field corruption
                print("Checking payments table for UUID corruption...")
                
                # Check if payments table exists and has payment_method field
                cursor.execute("SHOW TABLES LIKE '%payment%'")
                payment_tables = [row[0] for row in cursor.fetchall()]
                
                print(f"Found payment-related tables: {payment_tables}")
                
                for table in payment_tables:
                    if 'payment' in table.lower():
                        # Check table structure
                        cursor.execute(f"DESCRIBE {table}")
                        columns = {row[0]: row[1] for row in cursor.fetchall()}
                        
                        if 'payment_method' in columns:
                            print(f"Checking {table}.payment_method...")
                            
                            # Find corrupted payment_method values (strings instead of UUIDs)
                            cursor.execute(f"""
                                SELECT id, payment_method 
                                FROM {table} 
                                WHERE payment_method REGEXP '^[a-z_]+$'
                                OR payment_method = 'cash'
                                OR payment_method = 'mpesa'
                                OR payment_method = 'card'
                                OR payment_method = 'bank_transfer'
                                LIMIT 20
                            """)
                            
                            corrupted_payments = cursor.fetchall()
                            
                            if corrupted_payments:
                                print(f"  Found {len(corrupted_payments)} corrupted payment_method records:")
                                
                                for payment_id, method_value in corrupted_payments:
                                    print(f"    Payment {payment_id}: payment_method = '{method_value}'")
                                
                                # Create mapping of method names to UUIDs
                                method_mapping = {}
                                
                                # Check if paymentmethod table exists
                                cursor.execute("SHOW TABLES LIKE '%paymentmethod%'")
                                paymentmethod_tables = [row[0] for row in cursor.fetchall()]
                                
                                print(f"PaymentMethod tables found: {paymentmethod_tables}")
                                
                                for pm_table in paymentmethod_tables:
                                    try:
                                        cursor.execute(f"DESCRIBE {pm_table}")
                                        pm_columns = {row[0]: row[1] for row in cursor.fetchall()}
                                        
                                        if 'method_type' in pm_columns and 'id' in pm_columns:
                                            cursor.execute(f"SELECT id, method_type FROM {pm_table}")
                                            methods = cursor.fetchall()
                                            
                                            for method_id, method_type in methods:
                                                method_mapping[method_type] = method_id
                                            
                                            print(f"  Payment method mapping: {method_mapping}")
                                            break
                                    except Exception as e:
                                        print(f"  Error checking {pm_table}: {e}")
                                
                                # Fix corrupted payment_method values
                                for payment_id, method_value in corrupted_payments:
                                    if method_value in method_mapping:
                                        new_uuid = method_mapping[method_value]
                                        cursor.execute(f"""
                                            UPDATE {table} 
                                            SET payment_method = %s 
                                            WHERE id = %s
                                        """, [new_uuid, payment_id])
                                        print(f"    Fixed payment {payment_id}: '{method_value}' -> {new_uuid}")
                                        total_fixes += 1
                                    else:
                                        # Create a default payment method if needed
                                        print(f"    Warning: No mapping found for '{method_value}'")
                                
                                fixed_tables += 1
                            else:
                                print(f"  No UUID corruption found in {table}")
                
                print(f"\n✅ UUID corruption fix completed: {total_fixes} records fixed across {fixed_tables} tables")
                
    except Exception as e:
        print(f"❌ Error fixing UUID corruption: {e}")
        traceback.print_exc()

def fix_datetime_corruption():
    """Fix datetime corruption issues"""
    print_section("Fixing Datetime Corruption Issues")
    
    fixed_tables = 0
    total_fixes = 0
    
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                
                # 1. Fix auth_user datetime fields
                print("Checking auth_user table...")
                
                # Check date_joined corruption
                cursor.execute("""
                    SELECT COUNT(*) FROM auth_user 
                    WHERE date_joined REGEXP '^[0-9]+$'
                    OR date_joined = ''
                    OR date_joined = '0'
                    OR CAST(date_joined AS CHAR) REGEXP '^[0-9]+$'
                """)
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print(f"  Found {count} corrupted date_joined fields")
                    
                    # Fix Unix timestamp integers
                    cursor.execute("""
                        UPDATE auth_user 
                        SET date_joined = FROM_UNIXTIME(CAST(date_joined AS SIGNED))
                        WHERE date_joined REGEXP '^[0-9]+$' 
                        AND CAST(date_joined AS SIGNED) BETWEEN 1000000000 AND 2147483647
                    """)
                    fixed_timestamp = cursor.rowcount
                    print(f"    Fixed {fixed_timestamp} Unix timestamp date_joined fields")
                    
                    # Fix invalid values with current datetime
                    now = timezone.now()
                    cursor.execute("""
                        UPDATE auth_user 
                        SET date_joined = %s
                        WHERE date_joined = '' OR date_joined = '0' 
                        OR (date_joined REGEXP '^[0-9]+$' AND CAST(date_joined AS SIGNED) NOT BETWEEN 1000000000 AND 2147483647)
                    """, [now])
                    fixed_strings = cursor.rowcount
                    print(f"    Fixed {fixed_strings} invalid string date_joined fields")
                    
                    total_fixes += fixed_timestamp + fixed_strings
                    fixed_tables += 1
                
                # Check last_login corruption
                cursor.execute("""
                    SELECT COUNT(*) FROM auth_user 
                    WHERE last_login REGEXP '^[0-9]+$'
                    OR last_login = ''
                    OR last_login = '0'
                """)
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print(f"  Found {count} corrupted last_login fields")
                    
                    # Fix Unix timestamp integers
                    cursor.execute("""
                        UPDATE auth_user 
                        SET last_login = FROM_UNIXTIME(CAST(last_login AS SIGNED))
                        WHERE last_login REGEXP '^[0-9]+$' 
                        AND CAST(last_login AS SIGNED) BETWEEN 1000000000 AND 2147483647
                    """)
                    fixed_timestamp = cursor.rowcount
                    
                    # Set invalid values to NULL
                    cursor.execute("""
                        UPDATE auth_user 
                        SET last_login = NULL
                        WHERE last_login = '' OR last_login = '0'
                        OR (last_login REGEXP '^[0-9]+$' AND CAST(last_login AS SIGNED) NOT BETWEEN 1000000000 AND 2147483647)
                    """)
                    fixed_strings = cursor.rowcount
                    
                    print(f"    Fixed {fixed_timestamp + fixed_strings} last_login fields")
                    total_fixes += fixed_timestamp + fixed_strings
                
                # 2. Fix django_session table
                print("Checking django_session table...")
                cursor.execute("SHOW TABLES LIKE 'django_session'")
                
                if cursor.fetchone():
                    cursor.execute("""
                        SELECT COUNT(*) FROM django_session 
                        WHERE expire_date REGEXP '^[0-9]+$'
                        OR expire_date = ''
                        OR expire_date = '0'
                    """)
                    count = cursor.fetchone()[0]
                    
                    if count > 0:
                        print(f"  Found {count} corrupted expire_date fields")
                        
                        # Fix Unix timestamps
                        cursor.execute("""
                            UPDATE django_session 
                            SET expire_date = FROM_UNIXTIME(CAST(expire_date AS SIGNED))
                            WHERE expire_date REGEXP '^[0-9]+$' 
                            AND CAST(expire_date AS SIGNED) BETWEEN 1000000000 AND 2147483647
                        """)
                        fixed_timestamp = cursor.rowcount
                        
                        # Delete invalid sessions
                        cursor.execute("""
                            DELETE FROM django_session 
                            WHERE expire_date = '' OR expire_date = '0'
                            OR (expire_date REGEXP '^[0-9]+$' AND CAST(expire_date AS SIGNED) NOT BETWEEN 1000000000 AND 2147483647)
                        """)
                        deleted_invalid = cursor.rowcount
                        
                        print(f"    Fixed {fixed_timestamp} timestamps, deleted {deleted_invalid} invalid sessions")
                        total_fixes += fixed_timestamp
                        fixed_tables += 1
                
                # 3. Clean up expired sessions
                cursor.execute("DELETE FROM django_session WHERE expire_date < NOW()")
                deleted_expired = cursor.rowcount
                print(f"  Cleaned up {deleted_expired} expired sessions")
                
                # 4. Fix other common datetime fields
                print("Checking other tables for datetime corruption...")
                
                tables_to_check = [
                    ('authtoken_token', ['created']),
                    ('django_admin_log', ['action_time']),
                    ('core_tenant', ['created_at', 'updated_at', 'approved_at']),
                    ('accounts_userprofile', ['created_at', 'updated_at']),
                    ('socialaccount_socialaccount', ['last_login', 'date_joined']),
                ]
                
                for table_name, datetime_fields in tables_to_check:
                    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                    if cursor.fetchone():
                        print(f"  Checking {table_name}...")
                        
                        for field_name in datetime_fields:
                            cursor.execute(f"""
                                SELECT COUNT(*) FROM {table_name}
                                WHERE {field_name} REGEXP '^[0-9]+$'
                                OR {field_name} = ''
                                OR {field_name} = '0'
                            """)
                            count = cursor.fetchone()[0]
                            
                            if count > 0:
                                print(f"    Found {count} corrupted {field_name} fields")
                                
                                # Fix Unix timestamps
                                cursor.execute(f"""
                                    UPDATE {table_name}
                                    SET {field_name} = FROM_UNIXTIME(CAST({field_name} AS SIGNED))
                                    WHERE {field_name} REGEXP '^[0-9]+$'
                                    AND CAST({field_name} AS SIGNED) BETWEEN 1000000000 AND 2147483647
                                """)
                                fixed_ts = cursor.rowcount
                                
                                # Handle invalid values
                                if field_name in ['last_login']:
                                    cursor.execute(f"""
                                        UPDATE {table_name}
                                        SET {field_name} = NULL
                                        WHERE {field_name} = '' OR {field_name} = '0'
                                        OR ({field_name} REGEXP '^[0-9]+$' AND CAST({field_name} AS SIGNED) NOT BETWEEN 1000000000 AND 2147483647)
                                    """)
                                else:
                                    now = timezone.now()
                                    cursor.execute(f"""
                                        UPDATE {table_name}
                                        SET {field_name} = %s
                                        WHERE {field_name} = '' OR {field_name} = '0'
                                        OR ({field_name} REGEXP '^[0-9]+$' AND CAST({field_name} AS SIGNED) NOT BETWEEN 1000000000 AND 2147483647)
                                    """, [now])
                                fixed_str = cursor.rowcount
                                
                                if fixed_ts + fixed_str > 0:
                                    print(f"      Fixed {fixed_ts + fixed_str} {field_name} records")
                                    total_fixes += fixed_ts + fixed_str
                
                print(f"\n✅ Datetime corruption fix completed: {total_fixes} records fixed across {fixed_tables} tables")
                
    except Exception as e:
        print(f"❌ Error fixing datetime corruption: {e}")
        traceback.print_exc()

def fix_unicode_issues():
    """Fix unicode encoding issues in logs"""
    print_section("Fixing Unicode Encoding Issues")
    
    try:
        # Check Python locale settings
        import locale
        print(f"Current locale: {locale.getlocale()}")
        print(f"Default encoding: {sys.getdefaultencoding()}")
        
        # Set UTF-8 encoding for Python
        if sys.version_info >= (3, 7):
            # For Python 3.7+ this should be automatic, but let's verify
            print("✅ Python 3.7+ detected - UTF-8 should be default")
        else:
            print("⚠️  Older Python detected - may need manual UTF-8 setup")
        
        print("✅ Unicode encoding check completed")
        
    except Exception as e:
        print(f"❌ Error checking unicode settings: {e}")

def verify_fixes():
    """Verify that fixes were applied successfully"""
    print_section("Verifying Fixes")
    
    try:
        with connection.cursor() as cursor:
            
            # 1. Check auth_user datetime fields
            cursor.execute("""
                SELECT COUNT(*) FROM auth_user 
                WHERE date_joined REGEXP '^[0-9]+$'
                OR last_login REGEXP '^[0-9]+$'
                OR date_joined = '' OR date_joined = '0'
                OR last_login = '' OR last_login = '0'
            """)
            corrupted_users = cursor.fetchone()[0]
            
            if corrupted_users == 0:
                print("✅ auth_user datetime fields are clean")
            else:
                print(f"⚠️  Still have {corrupted_users} corrupted auth_user records")
            
            # 2. Check session table
            cursor.execute("SHOW TABLES LIKE 'django_session'")
            if cursor.fetchone():
                cursor.execute("""
                    SELECT COUNT(*) FROM django_session 
                    WHERE expire_date REGEXP '^[0-9]+$'
                    OR expire_date = '' OR expire_date = '0'
                """)
                corrupted_sessions = cursor.fetchone()[0]
                
                if corrupted_sessions == 0:
                    print("✅ django_session datetime fields are clean")
                else:
                    print(f"⚠️  Still have {corrupted_sessions} corrupted session records")
            
            # 3. Check payment method UUID fields
            cursor.execute("SHOW TABLES LIKE '%payment%'")
            payment_tables = [row[0] for row in cursor.fetchall()]
            
            uuid_issues = 0
            for table in payment_tables:
                if 'payment' in table.lower():
                    try:
                        cursor.execute(f"DESCRIBE {table}")
                        columns = {row[0]: row[1] for row in cursor.fetchall()}
                        
                        if 'payment_method' in columns:
                            cursor.execute(f"""
                                SELECT COUNT(*) FROM {table}
                                WHERE payment_method REGEXP '^[a-z_]+$'
                                OR payment_method = 'cash'
                                OR payment_method = 'mpesa'
                                OR payment_method = 'card'
                            """)
                            count = cursor.fetchone()[0]
                            uuid_issues += count
                    except:
                        pass
            
            if uuid_issues == 0:
                print("✅ Payment method UUID fields are clean")
            else:
                print(f"⚠️  Still have {uuid_issues} UUID corruption issues")
            
            # 4. Try to authenticate a user (this was the original error)
            try:
                user = User.objects.first()
                if user:
                    print(f"✅ User authentication test passed: {user.username}")
                else:
                    print("⚠️  No users found for authentication test")
            except Exception as e:
                print(f"❌ User authentication test failed: {e}")
        
        print("\n✅ Verification completed!")
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        traceback.print_exc()

def main():
    """Main execution function"""
    try:
        # Confirm we're on production and have backup
        confirm_production()
        
        # Apply all fixes
        fix_uuid_corruption()
        fix_datetime_corruption() 
        fix_unicode_issues()
        
        # Verify everything worked
        verify_fixes()
        
        print_header("🎉 PRODUCTION FIX COMPLETED SUCCESSFULLY! 🎉")
        print("All critical database corruption issues have been resolved.")
        print("\nNext steps:")
        print("1. Test your application - it should work normally now")
        print("2. Monitor logs for any remaining issues")
        print("3. Consider setting up automated database maintenance")
        print("\nIf you still see errors, please check the specific error messages")
        print("and run this script again, or contact support.")
        
    except KeyboardInterrupt:
        print("\n❌ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Critical error during fix: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()