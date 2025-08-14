from django.core.management.base import BaseCommand
from apps.customers.models import Customer
from apps.services.models import Service, ServiceOrder
from apps.payments.models import Payment
from apps.employees.models import Employee
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseRouter
from datetime import datetime


class Command(BaseCommand):
    help = 'Inspect actual data with dates for debugging'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-slug',
            type=str,
            required=True,
            help='Tenant slug to inspect data for'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data inspection...'))
        
        # Get the tenant
        try:
            tenant = Tenant.objects.get(slug=options['tenant_slug'])
            self.stdout.write(f'Found tenant: {tenant.name} ({tenant.slug})')
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant with slug "{options["tenant_slug"]}" not found'))
            return
        
        # Set the tenant context for database routing
        TenantDatabaseRouter.set_tenant(tenant)
        
        try:
            # Check recent orders with their dates
            self.stdout.write('\n=== Recent Orders ===')
            recent_orders = ServiceOrder.objects.all().order_by('-created_at')[:10]
            for order in recent_orders:
                self.stdout.write(f'Order {order.order_number}: {order.status} - {order.total_amount} - Created: {order.created_at}')
            
            # Check recent payments with their dates
            self.stdout.write('\n=== Recent Payments ===')
            recent_payments = Payment.objects.all().order_by('-initiated_at')[:10]
            for payment in recent_payments:
                completed_str = payment.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment.completed_at else 'Not completed'
                self.stdout.write(f'Payment {payment.payment_id}: {payment.status} - {payment.amount} - Created: {payment.initiated_at} - Completed: {completed_str}')
            
            # Check service order items
            self.stdout.write('\n=== Service Order Items ===')
            from apps.services.models import ServiceOrderItem
            recent_items = ServiceOrderItem.objects.all().order_by('-order__created_at')[:5]
            for item in recent_items:
                self.stdout.write(f'Item: {item.service.name} in Order {item.order.order_number} - {item.total_price} - Order Date: {item.order.created_at}')
            
            # Check employees
            self.stdout.write('\n=== Employees ===')
            employees = Employee.objects.all()
            for emp in employees:
                assigned_orders = emp.assigned_orders.count()
                service_items = emp.service_items.count()
                self.stdout.write(f'Employee {emp.employee_id}: Assigned Orders: {assigned_orders}, Service Items: {service_items}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error inspecting data: {str(e)}'))
            import traceback
            traceback.print_exc()
        
        finally:
            # Clear tenant context
            TenantDatabaseRouter.clear_tenant()
        
        self.stdout.write(self.style.SUCCESS('\nData inspection completed.'))
