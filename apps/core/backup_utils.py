import os
import json
import zipfile
import tempfile
import subprocess
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connections
from django.utils import timezone
from django.http import FileResponse, Http404
from apps.core.tenant_models import TenantBackup
import pandas as pd
import uuid


class TenantBackupManager:
    """Manager for creating and managing tenant database backups"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.tenant_db = f"tenant_{tenant.id}"
        
    def create_backup(self, backup_type='full', backup_format='sql', selected_tables=None, 
                     email_to=None, user=None):
        """Create a backup of the tenant database"""
        
        # Generate backup ID
        backup_id = f"backup_{self.tenant.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Create backup record
        backup = TenantBackup.objects.using('default').create(
            tenant_id=self.tenant.id,
            backup_id=backup_id,
            backup_type=backup_type,
            backup_format=backup_format,
            status='creating',
            created_by_user_id=user.id if user else None,
            expires_at=timezone.now() + timedelta(days=30)  # Default 30 days expiry
        )
        
        try:
            if backup_format == 'sql':
                file_path = self._create_sql_backup(backup, selected_tables)
            elif backup_format == 'json':
                file_path = self._create_json_backup(backup, selected_tables)
            elif backup_format == 'excel':
                file_path = self._create_excel_backup(backup, selected_tables)
            elif backup_format == 'csv':
                file_path = self._create_csv_backup(backup, selected_tables)
            else:
                raise ValueError(f"Unsupported backup format: {backup_format}")
            
            # Update backup record
            backup.status = 'completed'
            backup.completed_at = timezone.now()
            backup.file_path = file_path
            backup.file_name = os.path.basename(file_path)
            backup.file_size = os.path.getsize(file_path)
            backup.save(using='default')
            
            # Email backup if requested
            if email_to:
                self._email_backup(backup, email_to)
                backup.emailed_to = email_to
                backup.save(using='default')
            
            return backup
            
        except Exception as e:
            backup.status = 'failed'
            backup.error_message = str(e)
            backup.save(using='default')
            raise
    
    def _create_sql_backup(self, backup, selected_tables=None):
        """Create SQL dump backup"""
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', str(self.tenant.id))
        os.makedirs(backup_dir, exist_ok=True)
        
        file_path = os.path.join(backup_dir, f"{backup.backup_id}.sql")
        
        # Get database configuration
        db_config = self.tenant.database_config
        
        # For cPanel hosting, try mysqldump first, then fallback to Django-based backup
        try:
            # Create mysqldump command (works on most cPanel hosts)
            cmd = [
                'mysqldump',
                f'--host={db_config["HOST"]}',
                f'--port={db_config["PORT"]}',
                f'--user={db_config["USER"]}',
                f'--password={db_config["PASSWORD"]}',
                '--single-transaction',
                '--routines',
                '--triggers',
                '--no-create-db',
                db_config['NAME']
            ]
            
            # Add specific tables if partial backup
            if selected_tables and backup.backup_type == 'partial':
                cmd.extend(selected_tables)
            
            # Execute mysqldump
            with open(file_path, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                
            if result.returncode != 0:
                raise Exception(f"mysqldump failed: {result.stderr}")
                
        except (FileNotFoundError, Exception) as e:
            # Fallback to Django-based backup if mysqldump fails
            print(f"mysqldump failed ({e}), using Django-based backup...")
            return self._create_django_sql_backup(backup, selected_tables, file_path)
        
        # Get table counts
        record_counts = self._get_table_record_counts(selected_tables)
        backup.record_counts = record_counts
        backup.included_tables = list(record_counts.keys())
        
        return file_path
    
    def _create_django_sql_backup(self, backup, selected_tables, file_path):
        """Create SQL backup using Django database connection (fallback method)"""
        from django.db import connections
        
        # Get tables to export
        tables = selected_tables or self._get_all_tables()
        
        with open(file_path, 'w') as f:
            # Write SQL header
            f.write("-- Django-generated SQL backup\n")
            f.write("-- Generated on: {}\n\n".format(timezone.now().strftime('%Y-%m-%d %H:%M:%S')))
            f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")
            
            # Export each table
            with connections[self.tenant_db].cursor() as cursor:
                for table in tables:
                    try:
                        # Get table structure
                        cursor.execute(f"SHOW CREATE TABLE `{table}`")
                        create_sql = cursor.fetchone()[1]
                        f.write(f"-- Table: {table}\n")
                        f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                        f.write(f"{create_sql};\n\n")
                        
                        # Get table data
                        cursor.execute(f"SELECT * FROM `{table}`")
                        rows = cursor.fetchall()
                        
                        if rows:
                            columns = [desc[0] for desc in cursor.description]
                            f.write(f"-- Data for table: {table}\n")
                            f.write(f"INSERT INTO `{table}` (`{'`, `'.join(columns)}`) VALUES\n")
                            
                            for i, row in enumerate(rows):
                                values = []
                                for value in row:
                                    if value is None:
                                        values.append('NULL')
                                    elif isinstance(value, str):
                                        values.append(f"'{value.replace('\'', '\\\'')}'")
                                    else:
                                        values.append(str(value))
                                
                                if i == len(rows) - 1:
                                    f.write(f"({', '.join(values)});\n\n")
                                else:
                                    f.write(f"({', '.join(values)}),\n")
                        
                    except Exception as e:
                        f.write(f"-- Error exporting table {table}: {e}\n\n")
            
            f.write("SET FOREIGN_KEY_CHECKS = 1;\n")
        
        # Get table counts
        record_counts = self._get_table_record_counts(selected_tables)
        backup.record_counts = record_counts
        backup.included_tables = list(record_counts.keys())
        
        return file_path

    def _create_json_backup(self, backup, selected_tables=None):
        """Create JSON export backup"""
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', str(self.tenant.id))
        os.makedirs(backup_dir, exist_ok=True)
        
        file_path = os.path.join(backup_dir, f"{backup.backup_id}.json")
        
        # Get tables to export
        tables = selected_tables or self._get_all_tables()
        
        export_data = {}
        record_counts = {}
        
        with connections[self.tenant_db].cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f"SELECT * FROM {table}")
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    
                    # Convert to list of dictionaries
                    table_data = []
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            # Handle special data types
                            if hasattr(value, 'isoformat'):  # datetime objects
                                row_dict[columns[i]] = value.isoformat()
                            elif isinstance(value, (bytes, bytearray)):  # binary data
                                row_dict[columns[i]] = str(value)
                            else:
                                row_dict[columns[i]] = value
                        table_data.append(row_dict)
                    
                    export_data[table] = table_data
                    record_counts[table] = len(table_data)
                    
                except Exception as e:
                    print(f"Error exporting table {table}: {e}")
                    continue
        
        # Write JSON file
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        backup.record_counts = record_counts
        backup.included_tables = list(record_counts.keys())
        
        return file_path
    
    def _create_excel_backup(self, backup, selected_tables=None):
        """Create Excel export backup"""
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', str(self.tenant.id))
        os.makedirs(backup_dir, exist_ok=True)
        
        file_path = os.path.join(backup_dir, f"{backup.backup_id}.xlsx")
        
        # Get tables to export
        tables = selected_tables or self._get_all_tables()
        
        record_counts = {}
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            with connections[self.tenant_db].cursor() as cursor:
                for table in tables:
                    try:
                        cursor.execute(f"SELECT * FROM {table}")
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        
                        # Create DataFrame
                        df = pd.DataFrame(rows, columns=columns)
                        
                        # Write to Excel sheet
                        sheet_name = table[:30]  # Excel sheet name limit
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        record_counts[table] = len(df)
                        
                    except Exception as e:
                        print(f"Error exporting table {table}: {e}")
                        continue
        
        backup.record_counts = record_counts
        backup.included_tables = list(record_counts.keys())
        
        return file_path
    
    def _create_csv_backup(self, backup, selected_tables=None):
        """Create CSV export backup (zipped)"""
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', str(self.tenant.id))
        os.makedirs(backup_dir, exist_ok=True)
        
        zip_path = os.path.join(backup_dir, f"{backup.backup_id}.zip")
        
        # Get tables to export
        tables = selected_tables or self._get_all_tables()
        
        record_counts = {}
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            with connections[self.tenant_db].cursor() as cursor:
                for table in tables:
                    try:
                        cursor.execute(f"SELECT * FROM {table}")
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        
                        # Create DataFrame and save as CSV
                        df = pd.DataFrame(rows, columns=columns)
                        csv_content = df.to_csv(index=False)
                        
                        # Add to zip
                        zipf.writestr(f"{table}.csv", csv_content)
                        
                        record_counts[table] = len(df)
                        
                    except Exception as e:
                        print(f"Error exporting table {table}: {e}")
                        continue
        
        backup.record_counts = record_counts
        backup.included_tables = list(record_counts.keys())
        
        return zip_path
    
    def _get_all_tables(self):
        """Get list of all tables in tenant database"""
        with connections[self.tenant_db].cursor() as cursor:
            cursor.execute("SHOW TABLES")
            return [row[0] for row in cursor.fetchall()]
    
    def _get_table_record_counts(self, selected_tables=None):
        """Get record counts for tables"""
        tables = selected_tables or self._get_all_tables()
        record_counts = {}
        
        with connections[self.tenant_db].cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    record_counts[table] = count
                except Exception as e:
                    print(f"Error counting table {table}: {e}")
                    record_counts[table] = 0
        
        return record_counts
    
    def _email_backup(self, backup, email_to):
        """Email backup file to specified address"""
        try:
            from django.template.loader import render_to_string
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            
            # Prepare context for email template
            user_name = None
            if backup.created_by_user_id:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(id=backup.created_by_user_id)
                    user_name = user.get_full_name() or user.username
                except:
                    pass
            
            # Get the backup password for email context
            backup_password = self._get_business_owner_password()
            
            context = {
                'backup': backup,
                'user_name': user_name,
                'business_name': self.tenant.name,
                'business_email': self.tenant.email,
                'business_phone': self.tenant.phone,
                'app_name': getattr(settings, 'APP_NAME', 'Autowash'),
                'current_year': timezone.now().year,
                'is_password_protected': True,
                'backup_password': backup_password,
            }
            
            # Render email content
            subject = f"Database Backup Complete - {self.tenant.name}"
            html_message = render_to_string('emails/backup_notification.html', context)
            
            # Try to render text version
            try:
                plain_message = render_to_string('emails/backup_notification.txt', context)
            except:
                plain_message = f"Your database backup {backup.backup_id} has been created successfully."
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_to]
            )
            
            # Attach HTML version
            email.attach_alternative(html_message, "text/html")
            
            # Attach backup file with password protection
            if backup.file_path and os.path.exists(backup.file_path):
                # Create password-protected zip file
                protected_file_path = self._create_password_protected_backup(backup)
                if protected_file_path and os.path.exists(protected_file_path):
                    email.attach_file(protected_file_path)
                    # Clean up the temporary protected file after sending
                    try:
                        os.remove(protected_file_path)
                    except:
                        pass
                else:
                    # Fallback to original file if protection fails
                    email.attach_file(backup.file_path)
            
            email.send()
            
        except Exception as e:
            print(f"Error sending backup email: {e}")
            raise
    
    def _create_password_protected_backup(self, backup):
        """Create a password-protected zip file containing the backup using pyminizip"""
        try:
            import pyminizip
            
            # Get business owner's password
            password = self._get_business_owner_password()
            if not password:
                print("Warning: Could not retrieve business owner password for backup protection")
                return None
            
            # Create temporary protected file path
            backup_dir = os.path.dirname(backup.file_path)
            protected_filename = f"protected_{backup.backup_id}.zip"
            protected_file_path = os.path.join(backup_dir, protected_filename)
            
            # Create password-protected zip file using pyminizip (AES encryption)
            compression_level = 5  # 0-9, 5 is good balance of speed/compression
            pyminizip.compress(
                backup.file_path,           # Source file path
                None,                       # Path prefix in zip (None = use just filename)
                protected_file_path,        # Destination zip file path
                password,                   # Password for encryption
                compression_level           # Compression level
            )
            
            return protected_file_path
            
        except ImportError:
            print("Warning: pyminizip not available, falling back to standard zipfile")
            return self._create_fallback_protected_backup(backup)
        except Exception as e:
            print(f"Error creating password-protected backup with pyminizip: {e}")
            return self._create_fallback_protected_backup(backup)
    
    def _create_fallback_protected_backup(self, backup):
        """Fallback method using standard zipfile (less secure but still better than nothing)"""
        try:
            import zipfile
            
            password = self._get_business_owner_password()
            if not password:
                return None
            
            backup_dir = os.path.dirname(backup.file_path)
            protected_filename = f"protected_{backup.backup_id}.zip"
            protected_file_path = os.path.join(backup_dir, protected_filename)
            
            with zipfile.ZipFile(protected_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.setpassword(password.encode('utf-8'))
                zipf.write(backup.file_path, os.path.basename(backup.file_path))
            
            return protected_file_path
            
        except Exception as e:
            print(f"Error creating fallback protected backup: {e}")
            return None
    
    def _get_business_owner_password(self):
        """Generate a consistent password for backup protection based on business info"""
        try:
            # Create a deterministic password based on business information
            # This ensures the password is consistent and known to the business owner
            import hashlib
            
            # Use business ID + business name as the basis for password
            password_source = f"{self.tenant.id}_{self.tenant.slug}"
            password_hash = hashlib.sha256(password_source.encode()).hexdigest()
            
            # Create a human-readable password format: first 4 chars + last 4 chars
            password = f"{password_hash[:4]}{password_hash[-4:]}"
            
            return password.upper()  # Return in uppercase for easier typing
            
        except Exception as e:
            print(f"Error generating backup password: {e}")
            return None
    
    def get_backup_download_response(self, backup_id):
        """Get HTTP response for downloading backup"""
        try:
            backup = TenantBackup.objects.using('default').get(
                backup_id=backup_id,
                tenant_id=self.tenant.id,
                status='completed'
            )
            
            if backup.is_expired():
                raise Http404("Backup has expired")
            
            if not os.path.exists(backup.file_path):
                raise Http404("Backup file not found")
            
            # Determine content type
            if backup.backup_format == 'sql':
                content_type = 'application/sql'
            elif backup.backup_format == 'json':
                content_type = 'application/json'
            elif backup.backup_format == 'excel':
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif backup.backup_format == 'csv':
                content_type = 'application/zip'
            else:
                content_type = 'application/octet-stream'
            
            response = FileResponse(
                open(backup.file_path, 'rb'),
                content_type=content_type,
                as_attachment=True,
                filename=backup.file_name
            )
            
            return response
            
        except TenantBackup.DoesNotExist:
            raise Http404("Backup not found")
    
    def delete_backup(self, backup_id):
        """Delete a backup and its file"""
        try:
            backup = TenantBackup.objects.using('default').get(
                backup_id=backup_id,
                tenant_id=self.tenant.id
            )
            
            # Delete file if exists
            if backup.file_path and os.path.exists(backup.file_path):
                os.remove(backup.file_path)
            
            # Delete record
            backup.delete(using='default')
            
            return True
            
        except TenantBackup.DoesNotExist:
            return False
    
    def cleanup_expired_backups(self):
        """Clean up expired backups"""
        expired_backups = TenantBackup.objects.using('default').filter(
            tenant_id=self.tenant.id,
            expires_at__lt=timezone.now()
        )
        
        for backup in expired_backups:
            try:
                if backup.file_path and os.path.exists(backup.file_path):
                    os.remove(backup.file_path)
                backup.delete(using='default')
            except Exception as e:
                print(f"Error cleaning up backup {backup.backup_id}: {e}")


def get_table_mapping():
    """Get mapping of user-friendly names to actual table names"""
    return {
        'customers': 'customers_customer',
        'services': 'services_service',
        'payments': 'payments_payment',
        'employees': 'employees_employee',
        'inventory': 'inventory_inventoryitem',
        'orders': 'services_serviceorder',
        'suppliers': 'suppliers_supplier',
        'expenses': 'expenses_expense',
    }


def get_selected_tables(form_data):
    """Convert form selections to actual table names"""
    table_mapping = get_table_mapping()
    selected_tables = []
    
    for key, table_name in table_mapping.items():
        if form_data.get(f'include_{key}'):
            selected_tables.append(table_name)
    
    return selected_tables if selected_tables else None
