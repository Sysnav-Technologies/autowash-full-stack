"""
Django management command to fix corrupted UUID fields in the database.

This command addresses issues where UUID fields contain invalid data that causes
system crashes when clearing cache and accessing the database directly.

Usage:
    python manage.py fix_corrupted_uuids
    python manage.py fix_corrupted_uuids --dry-run
    python manage.py fix_corrupted_uuids --model=Tenant
    python manage.py fix_corrupted_uuids --field=subscription_id
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.conf import settings
import uuid
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix corrupted UUID fields in the database to prevent system crashes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--model',
            type=str,
            dest='model_name',
            help='Specific model to fix (e.g., Tenant, Subscription)',
        )
        parser.add_argument(
            '--field',
            type=str,
            dest='field_name',
            help='Specific UUID field to fix (e.g., id, subscription_id)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            dest='batch_size',
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.model_name = options['model_name']
        self.field_name = options['field_name']
        self.batch_size = options['batch_size']

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        self.stdout.write(
            self.style.HTTP_INFO('Starting UUID corruption cleanup...')
        )

        try:
            # Fix corrupted UUIDs in different models
            total_fixed = 0
            
            if not self.model_name or self.model_name.lower() == 'tenant':
                total_fixed += self.fix_tenant_uuids()
            
            if not self.model_name or self.model_name.lower() == 'subscription':
                total_fixed += self.fix_subscription_uuids()
            
            if not self.model_name or self.model_name.lower() == 'user':
                total_fixed += self.fix_user_related_uuids()
            
            # Always run MySQL connection cleanup unless specific model is targeted
            if not self.model_name:
                total_fixed += self.fix_mysql_connection_issues()

            if total_fixed > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Fixed {total_fixed} corrupted UUID fields'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('No corrupted UUID fields found')
                )

        except Exception as e:
            raise CommandError(f'Error fixing UUID corruption: {e}')

    def fix_tenant_uuids(self):
        """Fix corrupted UUIDs in Tenant model"""
        from apps.core.tenant_models import Tenant
        
        self.stdout.write('Checking Tenant model for UUID corruption...')
        
        fixed_count = 0
        
        # Check main ID field
        if not self.field_name or self.field_name == 'id':
            fixed_count += self._fix_uuid_field(Tenant, 'id', 'default')
        
        # Check subscription_id field if it exists
        if hasattr(Tenant._meta.get_field('subscription'), 'related_model'):
            if not self.field_name or self.field_name == 'subscription_id':
                fixed_count += self._fix_foreign_key_uuid_field(
                    Tenant, 'subscription', 'default'
                )
        
        return fixed_count

    def fix_subscription_uuids(self):
        """Fix corrupted UUIDs in Subscription model"""
        try:
            from apps.subscriptions.models import Subscription
        except ImportError:
            self.stdout.write(
                self.style.WARNING('Subscription model not found, skipping...')
            )
            return 0
        
        self.stdout.write('Checking Subscription model for UUID corruption...')
        
        fixed_count = 0
        
        # Check subscription_id field (primary UUID field)
        if not self.field_name or self.field_name == 'subscription_id':
            fixed_count += self._fix_uuid_field(
                Subscription, 'subscription_id', 'default'
            )
        
        # Check business_id field (foreign key to Tenant)
        if not self.field_name or self.field_name == 'business_id':
            fixed_count += self._fix_foreign_key_uuid_field(
                Subscription, 'business', 'default'
            )
        
        return fixed_count

    def fix_user_related_uuids(self):
        """Fix corrupted UUIDs in User-related models"""
        from django.contrib.auth import get_user_model
        
        self.stdout.write('Checking User-related models for UUID corruption...')
        
        User = get_user_model()
        fixed_count = 0
        
        # Check User model primary key
        if not self.field_name or self.field_name == 'id':
            fixed_count += self._fix_user_model_corruption(User)
        
        # Check for corrupted user sessions
        fixed_count += self._fix_user_session_corruption()
        
        return fixed_count

    def _fix_user_model_corruption(self, User):
        """Fix corrupted User model data causing list index out of range"""
        fixed_count = 0
        
        try:
            with connection.cursor() as cursor:
                # Check for corrupted user records that cause index errors
                table_name = User._meta.db_table
                
                # Get table structure to understand what might be corrupted
                cursor.execute(f"DESCRIBE {table_name}")
                columns = [row[0] for row in cursor.fetchall()]
                
                self.stdout.write(f'User table columns: {columns}')
                
                # Check for records with NULL or corrupted primary keys
                cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE id IS NULL OR id = ''")
                null_pk_count = cursor.fetchone()[0]
                
                if null_pk_count > 0:
                    self.stdout.write(
                        self.style.WARNING(f'Found {null_pk_count} user records with NULL/empty primary keys')
                    )
                    
                    if not self.dry_run:
                        # Delete records with NULL primary keys as they cause index errors
                        cursor.execute(f"DELETE FROM {table_name} WHERE id IS NULL OR id = ''")
                        fixed_count += null_pk_count
                        self.stdout.write(
                            self.style.SUCCESS(f'Removed {null_pk_count} corrupted user records')
                        )
                    else:
                        fixed_count += null_pk_count
                
                # Check for users with corrupted UUID fields (if User has UUID fields)
                uuid_fields = []
                for field in User._meta.fields:
                    if hasattr(field, 'get_internal_type') and 'UUID' in field.get_internal_type():
                        uuid_fields.append(field.column)
                
                for uuid_field in uuid_fields:
                    try:
                        cursor.execute(f"""
                            SELECT id, {uuid_field} 
                            FROM {table_name} 
                            WHERE {uuid_field} IS NOT NULL
                            LIMIT 100
                        """)
                        
                        for user_id, uuid_value in cursor.fetchall():
                            if uuid_value:
                                try:
                                    uuid.UUID(str(uuid_value))
                                except (ValueError, TypeError):
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'Found corrupted UUID in User.{uuid_field}: {uuid_value}'
                                        )
                                    )
                                    
                                    if not self.dry_run:
                                        # Generate new UUID for corrupted field
                                        new_uuid = uuid.uuid4()
                                        cursor.execute(f"""
                                            UPDATE {table_name} 
                                            SET {uuid_field} = %s 
                                            WHERE id = %s
                                        """, [str(new_uuid), user_id])
                                        fixed_count += 1
                                    else:
                                        fixed_count += 1
                    
                    except Exception as field_error:
                        self.stdout.write(
                            self.style.WARNING(f'Error checking User.{uuid_field}: {field_error}')
                        )
                        continue
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error checking User model corruption: {e}')
            )
        
        return fixed_count

    def _fix_user_session_corruption(self):
        """Fix corrupted user sessions that cause authentication errors"""
        fixed_count = 0
        
        try:
            with connection.cursor() as cursor:
                # Check django_session table for corrupted sessions
                cursor.execute("""
                    SELECT COUNT(*) FROM django_session 
                    WHERE session_data IS NULL 
                    OR session_data = '' 
                    OR expire_date < NOW()
                """)
                
                corrupted_sessions = cursor.fetchone()[0]
                
                if corrupted_sessions > 0:
                    self.stdout.write(
                        self.style.WARNING(f'Found {corrupted_sessions} corrupted/expired sessions')
                    )
                    
                    if not self.dry_run:
                        # Clean up corrupted and expired sessions
                        cursor.execute("""
                            DELETE FROM django_session 
                            WHERE session_data IS NULL 
                            OR session_data = '' 
                            OR expire_date < NOW()
                        """)
                        fixed_count += corrupted_sessions
                        self.stdout.write(
                            self.style.SUCCESS(f'Cleaned up {corrupted_sessions} corrupted sessions')
                        )
                    else:
                        fixed_count += corrupted_sessions
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error checking session corruption: {e}')
            )
        
        return fixed_count

    def _fix_uuid_field(self, model, field_name, database='default'):
        """Fix corrupted UUID values in a specific field"""
        fixed_count = 0
        
        try:
            # Get all records with potentially corrupted UUIDs
            records = model.objects.using(database).all()
            
            for record in records.iterator(chunk_size=self.batch_size):
                try:
                    field_value = getattr(record, field_name)
                    
                    if field_value:
                        # Try to validate the UUID
                        try:
                            uuid.UUID(str(field_value))
                        except (ValueError, TypeError):
                            # UUID is corrupted
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Found corrupted UUID in {model.__name__}.{field_name}: {field_value}'
                                )
                            )
                            
                            if not self.dry_run:
                                # Try to fix the UUID
                                fixed_uuid = self._attempt_uuid_repair(str(field_value))
                                if fixed_uuid:
                                    setattr(record, field_name, fixed_uuid)
                                    record.save(update_fields=[field_name])
                                    fixed_count += 1
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'Fixed {model.__name__}.{field_name}: {field_value} -> {fixed_uuid}'
                                        )
                                    )
                                else:
                                    # Cannot repair, generate new UUID
                                    new_uuid = uuid.uuid4()
                                    setattr(record, field_name, new_uuid)
                                    record.save(update_fields=[field_name])
                                    fixed_count += 1
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'Replaced {model.__name__}.{field_name}: {field_value} -> {new_uuid}'
                                        )
                                    )
                            else:
                                fixed_count += 1
                
                except Exception as record_error:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error processing record {record.pk}: {record_error}'
                        )
                    )
                    continue
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error checking {model.__name__}.{field_name}: {e}'
                )
            )
        
        return fixed_count

    def _fix_foreign_key_uuid_field(self, model, field_name, database='default'):
        """Fix corrupted UUID values in foreign key fields"""
        fixed_count = 0
        
        try:
            # Use raw SQL to check foreign key UUID fields
            with connection.cursor() as cursor:
                table_name = model._meta.db_table
                fk_field_name = f"{field_name}_id"
                
                # Find records with potentially corrupted foreign key UUIDs
                cursor.execute(f"""
                    SELECT id, {fk_field_name} 
                    FROM {table_name} 
                    WHERE {fk_field_name} IS NOT NULL
                """)
                
                records = cursor.fetchall()
                
                for record_id, fk_uuid_value in records:
                    if fk_uuid_value:
                        try:
                            uuid.UUID(str(fk_uuid_value))
                        except (ValueError, TypeError):
                            # Foreign key UUID is corrupted
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Found corrupted FK UUID in {model.__name__}.{fk_field_name}: {fk_uuid_value}'
                                )
                            )
                            
                            if not self.dry_run:
                                # Set foreign key to NULL (safer than trying to fix)
                                cursor.execute(f"""
                                    UPDATE {table_name} 
                                    SET {fk_field_name} = NULL 
                                    WHERE id = %s
                                """, [record_id])
                                fixed_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'Set {model.__name__}.{fk_field_name} to NULL for record {record_id}'
                                    )
                                )
                            else:
                                fixed_count += 1
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error checking FK field {model.__name__}.{field_name}: {e}'
                )
            )
        
        return fixed_count

    def _attempt_uuid_repair(self, corrupted_uuid):
        """Attempt to repair a corrupted UUID string"""
        try:
            # Remove any non-hex characters and try to reconstruct
            clean_uuid = ''.join(c for c in corrupted_uuid if c in '0123456789abcdefABCDEF-')
            
            # If it's 32 characters, try to format as UUID
            if len(clean_uuid) == 32:
                formatted_uuid = f"{clean_uuid[:8]}-{clean_uuid[8:12]}-{clean_uuid[12:16]}-{clean_uuid[16:20]}-{clean_uuid[20:]}"
                # Validate the formatted UUID
                uuid.UUID(formatted_uuid)
                return formatted_uuid
            
            # If it's already properly formatted, validate it
            if len(clean_uuid) == 36 and clean_uuid.count('-') == 4:
                uuid.UUID(clean_uuid)
                return clean_uuid
            
        except (ValueError, TypeError):
            pass
        
        return None

    def fix_mysql_connection_issues(self):
        """Fix MySQL connection and session issues that cause Command Out of Sync errors"""
        self.stdout.write('Checking for MySQL connection and session issues...')
        
        fixed_count = 0
        
        try:
            with connection.cursor() as cursor:
                # Check for long-running or stuck connections
                cursor.execute("SHOW PROCESSLIST")
                processes = cursor.fetchall()
                
                long_running_count = 0
                for process in processes:
                    # process format: (Id, User, Host, db, Command, Time, State, Info)
                    if len(process) >= 6 and process[5]:  # Check Time column
                        if process[5] > 300:  # More than 5 minutes
                            long_running_count += 1
                
                if long_running_count > 0:
                    self.stdout.write(
                        self.style.WARNING(f'Found {long_running_count} long-running connections')
                    )
                
                # Clean up expired sessions more aggressively
                cursor.execute("""
                    SELECT COUNT(*) FROM django_session 
                    WHERE expire_date < DATE_SUB(NOW(), INTERVAL 1 HOUR)
                """)
                old_sessions = cursor.fetchone()[0]
                
                if old_sessions > 0:
                    self.stdout.write(
                        self.style.WARNING(f'Found {old_sessions} old sessions (> 1 hour expired)')
                    )
                    
                    if not self.dry_run:
                        cursor.execute("""
                            DELETE FROM django_session 
                            WHERE expire_date < DATE_SUB(NOW(), INTERVAL 1 HOUR)
                        """)
                        fixed_count += old_sessions
                        self.stdout.write(
                            self.style.SUCCESS(f'Cleaned up {old_sessions} old sessions')
                        )
                    else:
                        fixed_count += old_sessions
                
                # Check for corrupted session data that might cause MySQL sync issues
                cursor.execute("""
                    SELECT session_key, session_data FROM django_session 
                    WHERE LENGTH(session_data) > 10000
                    LIMIT 10
                """)
                large_sessions = cursor.fetchall()
                
                if large_sessions:
                    self.stdout.write(
                        self.style.WARNING(f'Found {len(large_sessions)} unusually large sessions')
                    )
                    
                    for session_key, session_data in large_sessions:
                        # Check if session data is corrupted (contains binary or invalid data)
                        try:
                            session_data.encode('utf-8')
                        except UnicodeError:
                            if not self.dry_run:
                                cursor.execute("""
                                    DELETE FROM django_session WHERE session_key = %s
                                """, [session_key])
                                fixed_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f'Removed corrupted session: {session_key}')
                                )
                            else:
                                fixed_count += 1
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error checking MySQL connection issues: {e}')
            )
        
        return fixed_count