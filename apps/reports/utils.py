import csv
import json
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import xlsxwriter
import io
import os

class ReportGenerator:
    """Handles report data generation"""
    
    def __init__(self, template, report_instance):
        self.template = template
        self.report = report_instance
        self.start_time = timezone.now()
    
    def generate(self):
        """Generate report data based on template configuration"""
        try:
            # Get data based on template configuration
            data = self._get_report_data()
            
            # Apply aggregations
            summary = self._calculate_summary(data)
            
            # Generate charts data
            charts = self._generate_charts_data(data)
            
            # Update report instance
            self.report.report_data = data
            self.report.summary_data = summary
            self.report.charts_data = charts
            self.report.row_count = len(data) if isinstance(data, list) else 0
            
            # Generate files
            self._generate_files()
            
            # Mark as completed
            generation_time = (timezone.now() - self.start_time).total_seconds()
            self.report.mark_completed(generation_time)
            
        except Exception as e:
            self.report.mark_failed(str(e))
            raise e
    
    def _get_report_data(self):
        """Get raw data for the report"""
        data = []
        
        for source in self.template.data_sources:
            source_data = self._get_source_data(source)
            if isinstance(source_data, list):
                data.extend(source_data)
            else:
                data.append(source_data)
        
        return data
    
    def _get_source_data(self, source):
        """Get data from specific source"""
        from apps.customers.models import Customer
        from apps.services.models import ServiceOrder
        from apps.payments.models import Payment
        from apps.employees.models import Employee
        from .models import BusinessMetrics
        
        # Apply date filters
        date_filter = {
            'created_at__date__gte': self.report.date_from,
            'created_at__date__lte': self.report.date_to,
        }
        
        if source == 'customers':
            queryset = Customer.objects.filter(**date_filter)
            return [self._serialize_customer(c) for c in queryset]
        
        elif source == 'services':
            queryset = ServiceOrder.objects.filter(**date_filter)
            return [self._serialize_service(s) for s in queryset]
        
        elif source == 'payments':
            queryset = Payment.objects.filter(**date_filter)
            return [self._serialize_payment(p) for p in queryset]
        
        elif source == 'employees':
            queryset = Employee.objects.filter(is_active=True)
            return [self._serialize_employee(e) for e in queryset]
        
        elif source == 'metrics':
            queryset = BusinessMetrics.objects.filter(
                date__gte=self.report.date_from,
                date__lte=self.report.date_to
            )
            return [self._serialize_metrics(m) for m in queryset]
        
        return []
    
    def _serialize_customer(self, customer):
        """Serialize customer data"""
        return {
            'id': customer.id,
            'name': customer.full_name,
            'phone': str(customer.phone) if customer.phone else '',
            'email': customer.email,
            'is_vip': customer.is_vip,
            'total_visits': customer.total_visits,
            'total_spent': float(customer.total_spent or 0),
            'created_at': customer.created_at.isoformat(),
        }
    
    def _serialize_service(self, service):
        """Serialize service data"""
        return {
            'id': service.id,
            'customer_name': service.customer.full_name,
            'service_type': service.service.name,
            'status': service.status,
            'total_amount': float(service.total_amount),
            'created_at': service.created_at.isoformat(),
            'completed_at': service.completed_at.isoformat() if service.completed_at else None,
        }
    
    def _serialize_payment(self, payment):
        """Serialize payment data"""
        return {
            'id': payment.id,
            'amount': float(payment.amount),
            'method': payment.method,
            'status': payment.status,
            'customer_name': payment.customer.full_name if payment.customer else '',
            'created_at': payment.created_at.isoformat(),
        }
    
    def _serialize_employee(self, employee):
        """Serialize employee data"""
        return {
            'id': employee.id,
            'name': employee.full_name,
            'role': employee.role,
            'phone': str(employee.phone) if employee.phone else '',
            'email': employee.email,
            'hire_date': employee.hire_date.isoformat() if employee.hire_date else '',
        }
    
    def _serialize_metrics(self, metrics):
        """Serialize business metrics data"""
        return {
            'date': metrics.date.isoformat(),
            'total_revenue': float(metrics.total_revenue),
            'service_revenue': float(metrics.service_revenue),
            'total_customers': metrics.total_customers_served,
            'new_customers': metrics.new_customers,
            'total_services': metrics.total_services,
            'customer_satisfaction': float(metrics.customer_satisfaction),
            'profit': float(metrics.profit),
            'profit_margin': float(metrics.profit_margin),
        }
    
    def _calculate_summary(self, data):
        """Calculate summary statistics"""
        if not data:
            return {}
        
        summary = {
            'total_records': len(data),
            'date_range': f"{self.report.date_from} to {self.report.date_to}",
        }
        
        # Calculate aggregations based on template configuration
        for field, agg_type in self.template.aggregations.items():
            values = [item.get(field, 0) for item in data if isinstance(item.get(field), (int, float, Decimal))]
            
            if values:
                if agg_type == 'sum':
                    summary[f"{field}_total"] = sum(values)
                elif agg_type == 'avg':
                    summary[f"{field}_average"] = sum(values) / len(values)
                elif agg_type == 'count':
                    summary[f"{field}_count"] = len(values)
                elif agg_type == 'max':
                    summary[f"{field}_max"] = max(values)
                elif agg_type == 'min':
                    summary[f"{field}_min"] = min(values)
        
        return summary
    
    def _generate_charts_data(self, data):
        """Generate data for charts"""
        charts_data = {}
        
        for chart_config in self.template.charts:
            chart_type = chart_config.get('type', 'bar')
            chart_field = chart_config.get('field')
            chart_name = chart_config.get('name', f"{chart_field}_chart")
            
            if chart_field and chart_field in data[0] if data else False:
                if chart_type == 'pie':
                    charts_data[chart_name] = self._generate_pie_chart_data(data, chart_field)
                elif chart_type == 'line':
                    charts_data[chart_name] = self._generate_line_chart_data(data, chart_field)
                else:  # bar chart
                    charts_data[chart_name] = self._generate_bar_chart_data(data, chart_field)
        
        return charts_data
    
    def _generate_pie_chart_data(self, data, field):
        """Generate pie chart data"""
        from collections import Counter
        values = [item.get(field) for item in data if item.get(field)]
        counter = Counter(values)
        
        return {
            'labels': list(counter.keys()),
            'data': list(counter.values()),
            'type': 'pie'
        }
    
    def _generate_line_chart_data(self, data, field):
        """Generate line chart data"""
        # Group by date for time series
        by_date = {}
        for item in data:
            date_str = item.get('created_at', '')[:10]  # Get date part
            value = item.get(field, 0)
            if date_str:
                by_date[date_str] = by_date.get(date_str, 0) + (value if isinstance(value, (int, float)) else 1)
        
        sorted_dates = sorted(by_date.keys())
        return {
            'labels': sorted_dates,
            'data': [by_date[date] for date in sorted_dates],
            'type': 'line'
        }
    
    def _generate_bar_chart_data(self, data, field):
        """Generate bar chart data"""
        from collections import Counter
        values = [item.get(field) for item in data if item.get(field)]
        counter = Counter(values)
        
        return {
            'labels': list(counter.keys())[:10],  # Top 10
            'data': list(counter.values())[:10],
            'type': 'bar'
        }
    
    def _generate_files(self):
        """Generate PDF, Excel, and CSV files"""
        # Generate CSV
        csv_content = self._generate_csv()
        self.report.csv_file.save(
            f"report_{self.report.report_id}.csv",
            ContentFile(csv_content),
            save=False
        )
        
        # Generate Excel
        excel_content = self._generate_excel()
        self.report.excel_file.save(
            f"report_{self.report.report_id}.xlsx",
            ContentFile(excel_content),
            save=False
        )
        
        # Generate PDF
        pdf_content = self._generate_pdf()
        self.report.pdf_file.save(
            f"report_{self.report.report_id}.pdf",
            ContentFile(pdf_content),
            save=False
        )
    
    def _generate_csv(self):
        """Generate CSV content"""
        output = io.StringIO()
        
        if self.report.report_data:
            fieldnames = self.template.columns or self.report.report_data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in self.report.report_data:
                filtered_row = {k: v for k, v in row.items() if k in fieldnames}
                writer.writerow(filtered_row)
        
        return output.getvalue().encode('utf-8')
    
    def _generate_excel(self):
        """Generate Excel content"""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Report Data')
        
        # Add header format
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })
        
        if self.report.report_data:
            fieldnames = self.template.columns or list(self.report.report_data[0].keys())
            
            # Write headers
            for col, header in enumerate(fieldnames):
                worksheet.write(0, col, header, header_format)
            
            # Write data
            for row, data in enumerate(self.report.report_data, 1):
                for col, field in enumerate(fieldnames):
                    worksheet.write(row, col, data.get(field, ''))
        
        workbook.close()
        return output.getvalue()
    
    def _generate_pdf(self):
        """Generate PDF content"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph(f"<b>{self.template.name}</b>", styles['Title'])
        story.append(title)
        
        # Summary
        if self.report.summary_data:
            story.append(Paragraph("<b>Summary</b>", styles['Heading2']))
            for key, value in self.report.summary_data.items():
                story.append(Paragraph(f"{key}: {value}", styles['Normal']))
        
        # Data table (first 100 rows)
        if self.report.report_data:
            story.append(Paragraph("<b>Data</b>", styles['Heading2']))
            fieldnames = self.template.columns or list(self.report.report_data[0].keys())[:5]  # Limit columns
            
            table_data = [fieldnames]
            for row in self.report.report_data[:100]:  # Limit rows
                table_data.append([str(row.get(field, '')) for field in fieldnames])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
        
        doc.build(story)
        return buffer.getvalue()

class DashboardDataProvider:
    """Provides data for dashboard widgets"""
    
    def get_widget_data(self, widget):
        """Get data for a specific widget"""
        data_source = widget.data_source
        widget_type = widget.widget_type
        
        if data_source == 'metrics':
            return self._get_metrics_data(widget)
        elif data_source == 'customers':
            return self._get_customers_data(widget)
        elif data_source == 'services':
            return self._get_services_data(widget)
        elif data_source == 'payments':
            return self._get_payments_data(widget)
        
        return {}
    
    def _get_metrics_data(self, widget):
        """Get business metrics data"""
        from .models import BusinessMetrics
        
        # Get last 30 days of metrics
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        metrics = BusinessMetrics.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if widget.widget_type == 'metric':
            # Single metric widget
            field = widget.query_config.get('field', 'total_revenue')
            total = sum(getattr(m, field, 0) for m in metrics)
            return {'value': float(total), 'label': widget.title}
        
        elif widget.widget_type == 'chart':
            # Chart widget
            labels = [m.date.strftime('%Y-%m-%d') for m in metrics]
            field = widget.query_config.get('field', 'total_revenue')
            data = [float(getattr(m, field, 0)) for m in metrics]
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': widget.title,
                    'data': data,
                    'backgroundColor': widget.display_config.get('color', '#3b82f6')
                }]
            }
        
        return {}
    
    def _get_customers_data(self, widget):
        """Get customers data"""
        from apps.customers.models import Customer
        
        if widget.widget_type == 'metric':
            count = Customer.objects.count()
            return {'value': count, 'label': widget.title}
        
        elif widget.widget_type == 'chart':
            # Customers by registration date
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            
            customers = Customer.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(count=Count('id')).order_by('day')
            
            labels = [c['day'].strftime('%Y-%m-%d') for c in customers]
            data = [c['count'] for c in customers]
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'New Customers',
                    'data': data,
                    'backgroundColor': '#10b981'
                }]
            }
        
        return {}
    
    def _get_services_data(self, widget):
        """Get services data"""
        from apps.services.models import ServiceOrder
        
        if widget.widget_type == 'metric':
            field = widget.query_config.get('field', 'count')
            if field == 'count':
                value = ServiceOrder.objects.count()
            elif field == 'revenue':
                value = float(ServiceOrder.objects.aggregate(
                    total=Sum('total_amount')
                )['total'] or 0)
            else:
                value = 0
            
            return {'value': value, 'label': widget.title}
        
        elif widget.widget_type == 'chart':
            # Services by status
            services = ServiceOrder.objects.values('status').annotate(
                count=Count('id')
            )
            
            labels = [s['status'] for s in services]
            data = [s['count'] for s in services]
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'Services by Status',
                    'data': data,
                    'backgroundColor': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444']
                }]
            }
        
        return {}
    
    def _get_payments_data(self, widget):
        """Get payments data"""
        from apps.payments.models import Payment
        
        if widget.widget_type == 'metric':
            total = float(Payment.objects.filter(
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0)
            return {'value': total, 'label': widget.title}
        
        elif widget.widget_type == 'chart':
            # Payments by method
            payments = Payment.objects.filter(
                status='completed'
            ).values('method').annotate(
                total=Sum('amount')
            )
            
            labels = [p['method'] for p in payments]
            data = [float(p['total']) for p in payments]
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'Revenue by Payment Method',
                    'data': data,
                    'backgroundColor': ['#3b82f6', '#10b981', '#f59e0b']
                }]
            }
        
        return {}

class ReportExporter:
    """Handles report file exports"""
    
    def __init__(self, report):
        self.report = report
    
    def export(self, format_type):
        """Export report in specified format"""
        if format_type == 'pdf':
            return self._export_pdf()
        elif format_type == 'excel':
            return self._export_excel()
        elif format_type == 'csv':
            return self._export_csv()
        elif format_type == 'json':
            return self._export_json()
        
        raise ValueError(f"Unsupported format: {format_type}")
    
    def _export_pdf(self):
        """Export to PDF"""
        if self.report.pdf_file:
            return self.report.pdf_file.path
        raise ValueError("PDF file not generated")
    
    def _export_excel(self):
        """Export to Excel"""
        if self.report.excel_file:
            return self.report.excel_file.path
        raise ValueError("Excel file not generated")
    
    def _export_csv(self):
        """Export to CSV"""
        if self.report.csv_file:
            return self.report.csv_file.path
        raise ValueError("CSV file not generated")
    
    def _export_json(self):
        """Export to JSON"""
        # Create JSON file
        json_data = {
            'report_id': str(self.report.report_id),
            'template': self.report.template.name,
            'date_range': f"{self.report.date_from} to {self.report.date_to}",
            'generated_at': self.report.created_at.isoformat(),
            'data': self.report.report_data,
            'summary': self.report.summary_data,
            'charts': self.report.charts_data
        }
        
        # Save to file
        filename = f"report_{self.report.report_id}.json"
        filepath = os.path.join(settings.MEDIA_ROOT, 'reports', 'json', filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)
        
        return filepath

def calculate_business_metrics(date=None):
    """Calculate and save business metrics for a specific date"""
    from .models import BusinessMetrics
    from apps.customers.models import Customer
    from apps.services.models import ServiceOrder
    from apps.payments.models import Payment
    from apps.employees.models import Employee, Attendance
    
    if date is None:
        date = timezone.now().date()
    
    # Get or create metrics object
    metrics, created = BusinessMetrics.objects.get_or_create(
        date=date,
        defaults={}
    )
    
    # Calculate revenue metrics
    day_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
    day_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
    
    # Revenue calculations
    payments = Payment.objects.filter(
        status='completed',
        created_at__range=[day_start, day_end]
    )
    
    metrics.total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
    
    # Payment method breakdown
    metrics.cash_payments = payments.filter(method='cash').aggregate(
        total=Sum('amount'))['total'] or 0
    metrics.card_payments = payments.filter(method='card').aggregate(
        total=Sum('amount'))['total'] or 0
    metrics.mpesa_payments = payments.filter(method='mpesa').aggregate(
        total=Sum('amount'))['total'] or 0
    
    # Customer metrics
    customers = Customer.objects.filter(created_at__range=[day_start, day_end])
    metrics.new_customers = customers.count()
    
    # Service metrics
    services = ServiceOrder.objects.filter(created_at__range=[day_start, day_end])
    metrics.total_services = services.count()
    metrics.completed_services = services.filter(status='completed').count()
    metrics.cancelled_services = services.filter(status='cancelled').count()
    
    # Calculate service revenue
    service_revenue = services.filter(status='completed').aggregate(
        total=Sum('total_amount'))['total'] or 0
    metrics.service_revenue = service_revenue
    
    # Employee metrics
    attendance = Attendance.objects.filter(date=date)
    metrics.employees_present = attendance.filter(status='present').count()
    metrics.employees_absent = attendance.filter(status='absent').count()
    
    # Save metrics
    metrics.save()
    
    return metrics

def generate_scheduled_reports():
    """Generate all due scheduled reports"""
    from .models import ReportSchedule
    
    due_schedules = ReportSchedule.objects.filter(
        is_active=True,
        next_generation__lte=timezone.now()
    )
    
    for schedule in due_schedules:
        try:
            # Create report instance
            from .models import GeneratedReport
            report = GeneratedReport.objects.create(
                template=schedule.template,
                date_from=timezone.now().date() - timedelta(days=30),
                date_to=timezone.now().date(),
                status='generating'
            )
            
            # Generate report
            generator = ReportGenerator(schedule.template, report)
            generator.generate()
            
            # Send email if enabled
            if schedule.email_enabled and schedule.email_recipients:
                send_report_email(schedule, report)
            
            # Update schedule
            schedule.last_generated = timezone.now()
            schedule.generation_count += 1
            schedule.consecutive_failures = 0
            schedule.calculate_next_generation()
            
        except Exception as e:
            schedule.last_error = str(e)
            schedule.consecutive_failures += 1
            schedule.save()

def send_report_email(schedule, report):
    """Send report via email"""
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    
    subject = schedule.email_subject or f"Scheduled Report: {schedule.template.name}"
    
    context = {
        'schedule': schedule,
        'report': report,
        'business': schedule.template.business if hasattr(schedule.template, 'business') else None
    }
    
    html_content = render_to_string('reports/email/scheduled_report.html', context)
    
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=schedule.email_recipients
    )
    
    email.content_subtype = 'html'
    
    # Attach files if available
    if report.pdf_file:
        email.attach_file(report.pdf_file.path)
    if report.excel_file:
        email.attach_file(report.excel_file.path)
    
    email.send()

def track_analytics_event(event_type, event_data=None, customer=None, employee=None, request=None):
    """Track an analytics event"""
    from .models import AnalyticsEvent
    
    data = event_data or {}
    
    # Add request metadata if available
    if request:
        data.update({
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'session_id': request.session.session_key,
        })
    
    AnalyticsEvent.objects.create(
        event_type=event_type,
        event_data=data,
        customer=customer,
        employee=employee,
        ip_address=data.get('ip_address'),
        user_agent=data.get('user_agent', ''),
        session_id=data.get('session_id', '')
    )

def update_kpi_values():
    """Update all KPI current values based on their calculation methods"""
    from .models import KPI, BusinessMetrics
    from apps.customers.models import Customer
    from apps.services.models import ServiceOrder
    from apps.payments.models import Payment
    
    kpis = KPI.objects.filter(is_active=True)
    
    for kpi in kpis:
        try:
            if kpi.data_source == 'BusinessMetrics':
                # Get metrics for the measurement period
                if kpi.measurement_period == 'daily':
                    date = timezone.now().date()
                    metrics = BusinessMetrics.objects.filter(date=date).first()
                    if metrics:
                        kpi.current_value = getattr(metrics, kpi.calculation_method.split('.')[-1], 0)
                
                elif kpi.measurement_period == 'monthly':
                    start_date = timezone.now().date().replace(day=1)
                    metrics = BusinessMetrics.objects.filter(date__gte=start_date)
                    
                    if kpi.calculation_method.startswith('sum'):
                        field = kpi.calculation_method.split('.')[-1]
                        total = metrics.aggregate(total=Sum(field))['total'] or 0
                        kpi.current_value = total
            
            elif kpi.data_source == 'customers':
                if kpi.calculation_method == 'count':
                    kpi.current_value = Customer.objects.count()
            
            elif kpi.data_source == 'services':
                if kpi.calculation_method == 'count':
                    kpi.current_value = ServiceOrder.objects.count()
                elif kpi.calculation_method == 'revenue_sum':
                    total = ServiceOrder.objects.aggregate(
                        total=Sum('total_amount'))['total'] or 0
                    kpi.current_value = total
            
            kpi.last_calculated = timezone.now()
            kpi.save()
            
        except Exception as e:
            # Log error but continue with other KPIs
            print(f"Error updating KPI {kpi.name}: {e}")
            continue