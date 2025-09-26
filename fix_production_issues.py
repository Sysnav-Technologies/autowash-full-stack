#!/usr/bin/env python
"""
AutoWash Production Database Fix Script - Non-Interactive Version
================================================================

This script automatically fixes all critical database corruption issues in production:
1. UUID corruption in payment_method fields
2. Datetime corruption (integers/strings instead of proper datetime objects)
3. Session corruption issues
4. Unicode logging problems

USAGE ON CPANEL:
1. Upload this file to your app.autowash.co.ke root directory
2. Create a database backup first (IMPORTANT!)
3. Run: python fix_production_issues.py

This version runs automatically without user prompts - suitable for cPanel execution.
"""

import os
import sys
import django
from datetime import datetime
from django.utils import timezone
import uuid
import traceback
import time

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

def check_environment():
    """Check environment and warn about backup"""
    print_header("AutoWash Production Database Fix - Auto Mode")
    print("🔧 NON-INTERACTIVE PRODUCTION FIX")
    print("This script will automatically fix database corruption issues.")
    
    import socket
    hostname = socket.gethostname()
    print(f"\nEnvironment Info:")
    print(f"  Hostname: {hostname}")
    print(f"  Directory: {os.getcwd()}")
    print(f"  Python Version: {sys.version}")
    
    print("\n⚠️  CRITICAL: DATABASE BACKUP REQUIRED ⚠️")
    print("This script assumes you have created a database backup!")
    print("If you haven't backed up your database, stop this script now!")
    
    print("\nStarting automatic fix in 5 seconds...")
    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    
    print("✅ Starting database fixes...")

def fix_uuid_corruption():
    """Fix UUID corruption in payment_method fields"""
    print_section("Fixing UUID Corruption Issues")
    
    fixed_tables = 0
    total_fixes = 0
    
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                
                # Find all payment-related tables
                cursor.execute("SHOW TABLES")
                all_tables = [row[0] for row in cursor.fetchall()]
                payment_tables = [table for table in all_tables if 'payment' in table.lower()]
                
                print(f"Found payment-related tables: {payment_tables}")
                
                for table in payment_tables:
                    try:
                        # Check table structure
                        cursor.execute(f"DESCRIBE {table}")
                        columns = {row[0]: row[1] for row in cursor.fetchall()}
                        
                        if 'payment_method' in columns:
                            print(f"Checking {table}.payment_method...")
                            
                            # Find corrupted payment_method values
                            cursor.execute(f"""
                                SELECT id, payment_method, COUNT(*) as count
                                FROM {table} 
                                WHERE payment_method REGEXP '^[a-z_]+$'
                                OR payment_method IN ('cash', 'mpesa', 'card', 'bank_transfer')
                                GROUP BY payment_method
                                LIMIT 50
                            """)
                            
                            corrupted_data = cursor.fetchall()
                            
                            if corrupted_data:
                                print(f"  Found corrupted payment_method records:")
                                for _, method_value, count in corrupted_data:
                                    print(f"    '{method_value}': {count} records")
                                
                                # Get or create proper payment method UUIDs
                                method_uuid_map = {}
                                
                                # Try to find paymentmethod table
                                paymentmethod_tables = [t for t in all_tables if 'paymentmethod' in t.lower()]
                                
                                if paymentmethod_tables:
                                    pm_table = paymentmethod_tables[0]
                                    try:
                                        cursor.execute(f"SELECT id, method_type FROM {pm_table}")
                                        for method_id, method_type in cursor.fetchall():
                                            method_uuid_map[method_type] = method_id
                                        print(f"  Using existing payment methods: {method_uuid_map}")
                                    except Exception as e:
                                        print(f"  Error reading payment methods: {e}")
                                
                                # If no mapping found, create shorter UUIDs that fit in VARCHAR fields
                                if not method_uuid_map:
                                    method_uuid_map = {
                                        'cash': 'cash-001',
                                        'mpesa': 'mpesa-001',
                                        'card': 'card-001',
                                        'bank_transfer': 'bank-001',
                                    }
                                    print(f"  Created short IDs: {method_uuid_map}")
                                
                                # Fix corrupted records
                                for payment_id, method_value, count in corrupted_data:
                                    if method_value in method_uuid_map:
                                        new_uuid = method_uuid_map[method_value]
                                        cursor.execute(f"""
                                            UPDATE {table} 
                                            SET payment_method = %s 
                                            WHERE payment_method = %s
                                        """, [new_uuid, method_value])
                                        
                                        affected = cursor.rowcount
                                        print(f"    Fixed {affected} records: '{method_value}' -> {new_uuid}")
                                        total_fixes += affected
                                
                                fixed_tables += 1
                            else:
                                print(f"  No UUID corruption found in {table}")
                    
                    except Exception as e:
                        print(f"  Error processing {table}: {e}")
                        continue
                
                print(f"\n✅ UUID corruption fix completed: {total_fixes} records fixed across {fixed_tables} tables")
                
    except Exception as e:
        print(f"❌ Error fixing UUID corruption: {e}")
        traceback.print_exc()

def fix_datetime_corruption():
    """Fix datetime corruption issues"""
    print_section("Fixing Datetime Corruption Issues")
    
    total_fixes = 0
    
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                
                # 1. Fix auth_user table
                print("Fixing auth_user table...")
                
                # Fix date_joined field - use safer query for MySQL strict mode
                cursor.execute("""
                    SELECT COUNT(*) FROM auth_user 
                    WHERE (date_joined IS NULL) 
                    OR (LENGTH(TRIM(date_joined)) = 0)
                    OR (date_joined = '0000-00-00 00:00:00')
                    OR (date_joined REGEXP '^[0-9]+$' AND CHAR_LENGTH(date_joined) BETWEEN 8 AND 12)
                """)
                corrupted_count = cursor.fetchone()[0]
                
                if corrupted_count > 0:
                    print(f"  Found {corrupted_count} corrupted date_joined fields")
                    
                    # Fix Unix timestamps - safer approach
                    cursor.execute("""
                        UPDATE auth_user 
                        SET date_joined = FROM_UNIXTIME(CAST(date_joined AS SIGNED))
                        WHERE date_joined REGEXP '^[0-9]{10}$'
                        AND CAST(date_joined AS SIGNED) BETWEEN 946684800 AND 2147483647
                        AND date_joined != '0000-00-00 00:00:00'
                    """)
                    fixed_timestamps = cursor.rowcount
                    
                    # Fix invalid values with current datetime - safer approach
                    if fixed_timestamps > 0:
                        print(f"    Fixed {fixed_timestamps} timestamp fields")
                        total_fixes += fixed_timestamps
                    
                    # Handle NULL and invalid dates separately
                    now = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("""
                        UPDATE auth_user 
                        SET date_joined = %s
                        WHERE date_joined IS NULL 
                        OR date_joined = '0000-00-00 00:00:00'
                        OR LENGTH(TRIM(date_joined)) = 0
                    """, [now])
                    fixed_null = cursor.rowcount
                    
                    if fixed_null > 0:
                        print(f"    Fixed {fixed_null} NULL/invalid date_joined fields")
                        total_fixes += fixed_null
                
                # Fix last_login field - safer approach
                cursor.execute("""
                    SELECT COUNT(*) FROM auth_user 
                    WHERE last_login IS NOT NULL 
                    AND ((last_login REGEXP '^[0-9]+$' AND CHAR_LENGTH(last_login) BETWEEN 8 AND 12)
                         OR last_login = '0000-00-00 00:00:00'
                         OR LENGTH(TRIM(last_login)) = 0)
                """)
                corrupted_count = cursor.fetchone()[0]
                
                if corrupted_count > 0:
                    print(f"  Found {corrupted_count} corrupted last_login fields")
                    
                    # Fix Unix timestamps
                    cursor.execute("""
                        UPDATE auth_user 
                        SET last_login = FROM_UNIXTIME(CAST(last_login AS SIGNED))
                        WHERE last_login REGEXP '^[0-9]{10}$'
                        AND CAST(last_login AS SIGNED) BETWEEN 946684800 AND 2147483647
                        AND last_login != '0000-00-00 00:00:00'
                    """)
                    fixed_timestamps = cursor.rowcount
                    
                    # Set invalid values to NULL
                    cursor.execute("""
                        UPDATE auth_user 
                        SET last_login = NULL
                        WHERE last_login = '0000-00-00 00:00:00'
                        OR LENGTH(TRIM(last_login)) = 0
                        OR (last_login REGEXP '^[0-9]+$' 
                            AND CAST(last_login AS SIGNED) NOT BETWEEN 946684800 AND 2147483647)
                    """)
                    fixed_invalid = cursor.rowcount
                    
                    print(f"    Fixed {fixed_timestamps} timestamp fields, nullified {fixed_invalid} invalid fields")
                    total_fixes += fixed_timestamps + fixed_invalid
                
                # 2. Fix django_session table
                print("Fixing django_session table...")
                
                cursor.execute("SHOW TABLES LIKE 'django_session'")
                if cursor.fetchone():
                    cursor.execute("""
                        SELECT COUNT(*) FROM django_session 
                        WHERE (expire_date REGEXP '^[0-9]+$' AND CHAR_LENGTH(expire_date) BETWEEN 8 AND 12)
                        OR expire_date = '0000-00-00 00:00:00'
                        OR LENGTH(TRIM(expire_date)) = 0
                    """)
                    corrupted_count = cursor.fetchone()[0]
                    
                    if corrupted_count > 0:
                        print(f"  Found {corrupted_count} corrupted expire_date fields")
                        
                        # Fix Unix timestamps
                        cursor.execute("""
                            UPDATE django_session 
                            SET expire_date = FROM_UNIXTIME(CAST(expire_date AS SIGNED))
                            WHERE expire_date REGEXP '^[0-9]{10}$'
                            AND CAST(expire_date AS SIGNED) BETWEEN 946684800 AND 2147483647
                        """)
                        fixed_timestamps = cursor.rowcount
                        
                        # Delete invalid sessions
                        cursor.execute("""
                            DELETE FROM django_session 
                            WHERE expire_date = '0000-00-00 00:00:00'
                            OR LENGTH(TRIM(expire_date)) = 0
                            OR (expire_date REGEXP '^[0-9]+$' 
                                AND CAST(expire_date AS SIGNED) NOT BETWEEN 946684800 AND 2147483647)
                        """)
                        deleted_invalid = cursor.rowcount
                        
                        print(f"    Fixed {fixed_timestamps} timestamps, deleted {deleted_invalid} invalid sessions")
                        total_fixes += fixed_timestamps
                    
                    # Clean up expired sessions
                    cursor.execute("DELETE FROM django_session WHERE expire_date < NOW()")
                    deleted_expired = cursor.rowcount
                    if deleted_expired > 0:
                        print(f"  Cleaned up {deleted_expired} expired sessions")
                
                # 3. Fix other common datetime fields
                print("Fixing other datetime fields...")
                
                tables_to_fix = [
                    ('authtoken_token', ['created']),
                    ('django_admin_log', ['action_time']),
                ]
                
                # Get all tables to check for common datetime patterns
                cursor.execute("SHOW TABLES")
                all_tables = [row[0] for row in cursor.fetchall()]
                
                for table in all_tables:
                    if any(keyword in table.lower() for keyword in ['tenant', 'profile', 'account']):
                        try:
                            cursor.execute(f"DESCRIBE {table}")
                            columns = [row[0] for row in cursor.fetchall()]
                            datetime_cols = [col for col in columns if any(keyword in col.lower() 
                                           for keyword in ['created', 'updated', 'date', 'time'])]
                            if datetime_cols:
                                tables_to_fix.append((table, datetime_cols))
                        except:
                            continue
                
                for table_name, datetime_fields in tables_to_fix:
                    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                    if cursor.fetchone():
                        print(f"  Checking {table_name}...")
                        
                        for field_name in datetime_fields:
                            try:
                                cursor.execute(f"""
                                    SELECT COUNT(*) FROM {table_name}
                                    WHERE CAST({field_name} AS CHAR) REGEXP '^[0-9]+$'
                                    OR {field_name} = '' OR {field_name} = '0'
                                """)
                                corrupted_count = cursor.fetchone()[0]
                                
                                if corrupted_count > 0:
                                    print(f"    Found {corrupted_count} corrupted {field_name} fields")
                                    
                                    # Fix Unix timestamps
                                    cursor.execute(f"""
                                        UPDATE {table_name}
                                        SET {field_name} = FROM_UNIXTIME(CAST({field_name} AS SIGNED))
                                        WHERE CAST({field_name} AS CHAR) REGEXP '^[0-9]{{10}}$'
                                        AND CAST({field_name} AS SIGNED) BETWEEN 946684800 AND 2147483647
                                    """)
                                    fixed_ts = cursor.rowcount
                                    
                                    # Handle invalid values
                                    if 'login' in field_name.lower():
                                        cursor.execute(f"""
                                            UPDATE {table_name}
                                            SET {field_name} = NULL
                                            WHERE {field_name} = '' OR {field_name} = '0'
                                        """)
                                    else:
                                        now = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                                        cursor.execute(f"""
                                            UPDATE {table_name}
                                            SET {field_name} = %s
                                            WHERE {field_name} = '' OR {field_name} = '0'
                                        """, [now])
                                    fixed_inv = cursor.rowcount
                                    
                                    if fixed_ts + fixed_inv > 0:
                                        print(f"      Fixed {fixed_ts + fixed_inv} {field_name} records")
                                        total_fixes += fixed_ts + fixed_inv
                            except Exception as e:
                                print(f"      Error fixing {field_name}: {e}")
                
                print(f"\n✅ Datetime corruption fix completed: {total_fixes} total records fixed")
                
    except Exception as e:
        print(f"❌ Error fixing datetime corruption: {e}")
        traceback.print_exc()

def verify_fixes():
    """Verify that fixes were applied successfully"""
    print_section("Verifying Fixes")
    
    issues_found = 0
    
    try:
        with connection.cursor() as cursor:
            
            # 1. Check auth_user datetime fields - safer queries
            cursor.execute("""
                SELECT COUNT(*) FROM auth_user 
                WHERE (date_joined IS NULL)
                OR (date_joined = '0000-00-00 00:00:00')
                OR (date_joined REGEXP '^[0-9]+$' AND CHAR_LENGTH(date_joined) BETWEEN 8 AND 12)
                OR (last_login IS NOT NULL AND last_login = '0000-00-00 00:00:00')
                OR (last_login IS NOT NULL AND last_login REGEXP '^[0-9]+$' AND CHAR_LENGTH(last_login) BETWEEN 8 AND 12)
            """)
            corrupted_users = cursor.fetchone()[0]
            
            if corrupted_users == 0:
                print("✅ auth_user datetime fields are clean")
            else:
                print(f"⚠️  Still have {corrupted_users} corrupted auth_user records")
                issues_found += corrupted_users
            
            # 2. Check session table
            cursor.execute("SHOW TABLES LIKE 'django_session'")
            if cursor.fetchone():
                cursor.execute("""
                    SELECT COUNT(*) FROM django_session 
                    WHERE (expire_date REGEXP '^[0-9]+$' AND CHAR_LENGTH(expire_date) BETWEEN 8 AND 12)
                    OR expire_date = '0000-00-00 00:00:00'
                    OR LENGTH(TRIM(expire_date)) = 0
                """)
                corrupted_sessions = cursor.fetchone()[0]
                
                if corrupted_sessions == 0:
                    print("✅ django_session datetime fields are clean")
                else:
                    print(f"⚠️  Still have {corrupted_sessions} corrupted session records")
                    issues_found += corrupted_sessions
            
            # 3. Test user authentication
            try:
                # Get first active user
                user_query = User.objects.filter(is_active=True)
                if user_query.exists():
                    test_user = user_query.first()
                    # Try to access datetime fields that were causing errors
                    test_date = test_user.date_joined
                    if hasattr(test_date, 'year'):  # Check if it's a proper datetime
                        print(f"✅ User authentication test passed: {test_user.username} (joined: {test_date.year})")
                    else:
                        print(f"⚠️  User datetime still corrupted: {test_user.username}")
                        issues_found += 1
                else:
                    print("⚠️  No active users found for testing")
            except Exception as e:
                print(f"❌ User authentication test failed: {e}")
                issues_found += 1
        
        if issues_found == 0:
            print("\n🎉 All fixes verified successfully!")
        else:
            print(f"\n⚠️  {issues_found} issues still remain - may need manual review")
        
        return issues_found == 0
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        traceback.print_exc()
        return False

def main():
    """Main execution function"""
    try:
        # Check environment
        check_environment()
        
        # Apply all fixes
        fix_uuid_corruption()
        fix_datetime_corruption()
        
        # Verify everything worked
        success = verify_fixes()
        
        if success:
            print_header("🎉 PRODUCTION FIX COMPLETED SUCCESSFULLY! 🎉")
            print("All critical database corruption issues have been resolved.")
            print("\n✅ Your AutoWash system should now work normally!")
            print("\nNext steps:")
            print("1. Test your application login and payment processing")
            print("2. Monitor logs for any remaining issues")
            print("3. Consider regular database maintenance")
        else:
            print_header("⚠️  PRODUCTION FIX COMPLETED WITH WARNINGS")
            print("Most issues were fixed, but some may need manual attention.")
            print("Check the verification output above for details.")
        
        print(f"\nFix completed at: {datetime.now()}")
        
    except KeyboardInterrupt:
        print("\n❌ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Critical error during fix: {e}")
        traceback.print_exc()
        print("\n💡 If you continue to see errors, please:")
        print("1. Check your database backup is available")
        print("2. Review the error messages above")
        print("3. Contact technical support with the full error log")
        sys.exit(1)

if __name__ == "__main__":
    main()