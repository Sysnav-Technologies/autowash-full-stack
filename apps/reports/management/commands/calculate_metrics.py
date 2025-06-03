# apps/reports/management/commands/calculate_metrics.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from apps.reports.utils import calculate_business_metrics, update_kpi_values

class Command(BaseCommand):
    help = 'Calculate business metrics for specified date range'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to calculate metrics for (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to calculate metrics for (default: 1)'
        )
        parser.add_argument(
            '--update-kpis',
            action='store_true',
            help='Also update KPI values after calculating metrics'
        )
        parser.add_argument(
            '--backfill',
            type=int,
            help='Backfill metrics for the last N days'
        )
    
    def handle(self, *args, **options):
        if options['backfill']:
            # Backfill for the last N days
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=options['backfill'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Backfilling metrics from {start_date} to {end_date}'
                )
            )
            
            current_date = start_date
            while current_date <= end_date:
                try:
                    metrics = calculate_business_metrics(current_date)
                    self.stdout.write(f'✓ Calculated metrics for {current_date}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to calculate metrics for {current_date}: {e}')
                    )
                current_date += timedelta(days=1)
        
        elif options['date']:
            # Calculate for specific date
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                metrics = calculate_business_metrics(target_date)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Calculated metrics for {target_date}')
                )
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error calculating metrics: {e}')
                )
                return
        
        else:
            # Calculate for the last N days (default: 1)
            days = options['days']
            end_date = timezone.now().date()
            
            for i in range(days):
                target_date = end_date - timedelta(days=i)
                try:
                    metrics = calculate_business_metrics(target_date)
                    self.stdout.write(f'✓ Calculated metrics for {target_date}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to calculate metrics for {target_date}: {e}')
                    )
        
        # Update KPIs if requested
        if options['update_kpis']:
            try:
                update_kpi_values()
                self.stdout.write(
                    self.style.SUCCESS('✓ Updated KPI values')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to update KPIs: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Metrics calculation completed!')
        )