# apps/employees/models.py - Fixed to avoid FK constraint to User

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.models import TimeStampedModel, SoftDeleteModel, Address, ContactInfo
from apps.core.utils import upload_to_path
from decimal import Decimal
from django_tenants.utils import schema_context, get_public_schema_name

class Department(TimeStampedModel):
    """Department model for organizing employees"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey(
        'Employee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='headed_department'
    )
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    @property
    def employee_count(self):
        return self.employees.filter(is_active=True).count()
    
    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ['name']

class Position(TimeStampedModel):
    """Job position model"""
    title = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='positions')
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    min_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.title} - {self.department.name}"
    
    class Meta:
        verbose_name = "Position"
        verbose_name_plural = "Positions"
        ordering = ['title']

class Employee(SoftDeleteModel, Address, ContactInfo):
    """Employee model with comprehensive information - Fixed for django-tenants"""
    
    ROLE_CHOICES = [
        ('owner', 'Business Owner'),
        ('manager', 'Manager'),
        ('supervisor', 'Supervisor'),
        ('attendant', 'Service Attendant'),
        ('cashier', 'Cashier'),
        ('cleaner', 'Cleaner'),
        ('security', 'Security Guard'),
    ]
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ]
    
    # IMPORTANT: Use user_id instead of OneToOneField to avoid FK constraint
    # Nullable initially to allow smooth migration, will be populated automatically
    user_id = models.IntegerField(null=True, blank=True, unique=True)  # Store user ID from public schema
    
    # Basic Information
    employee_id = models.CharField(max_length=20, unique=True)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        blank=True
    )
    marital_status = models.CharField(
        max_length=20,
        choices=[
            ('single', 'Single'),
            ('married', 'Married'),
            ('divorced', 'Divorced'),
            ('widowed', 'Widowed'),
        ],
        blank=True
    )
    national_id = models.CharField(max_length=20, blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = PhoneNumberField(blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True)
    
    # Employment Information
    department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='employees'
    )
    position = models.ForeignKey(
        Position, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='employees'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='attendant')
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='full_time')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Dates
    hire_date = models.DateField()
    probation_end_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Compensation
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    can_login = models.BooleanField(default=True)
    receive_notifications = models.BooleanField(default=True)
    
    # Supervisor
    supervisor = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='subordinates'
    )
    
    # Performance
    performance_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    def __str__(self):
        return f"{self.full_name} ({self.employee_id})"
    
    def save(self, *args, **kwargs):
        # Auto-populate user_id from user if not set
        if hasattr(self, 'user') and self.user and not self.user_id:
            self.user_id = self.user.id
        super().save(*args, **kwargs)
    
    @property
    def user(self):
        """Get user object from public schema"""
        if not self.user_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.user_id)
        except User.DoesNotExist:
            return None
    
    @property
    def full_name(self):
        user = self.user
        if user:
            return user.get_full_name() or user.username
        return f"User ID {self.user_id}"
    
    @property
    def username(self):
        user = self.user
        return user.username if user else f"user_{self.user_id}"
    
    @property
    def email(self):
        user = self.user
        return user.email if user else ""
    
    @property
    def first_name(self):
        user = self.user
        return user.first_name if user else ""
    
    @property
    def last_name(self):
        user = self.user
        return user.last_name if user else ""
    
    @property
    def age(self):
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
    
    @property
    def years_of_service(self):
        from datetime import date
        today = date.today()
        return today.year - self.hire_date.year - ((today.month, today.day) < (self.hire_date.month, self.hire_date.day))
    
    def can_manage_employee(self, employee):
        """Check if this employee can manage another employee"""
        if self.role == 'owner':
            return True
        elif self.role == 'manager':
            return employee.role not in ['owner', 'manager'] or employee.supervisor == self
        elif self.role == 'supervisor':
            return employee.supervisor == self
        return False
    
    def get_subordinates(self):
        """Get all subordinates under this employee"""
        if self.role in ['owner', 'manager']:
            return Employee.objects.filter(is_active=True).exclude(id=self.id)
        elif self.role == 'supervisor':
            return self.subordinates.filter(is_active=True)
        return Employee.objects.none()
    
    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ['employee_id']

class EmployeeDocument(TimeStampedModel):
    """Employee document storage"""
    
    DOCUMENT_TYPES = [
        ('cv', 'CV/Resume'),
        ('id_copy', 'ID Copy'),
        ('certificate', 'Certificate'),
        ('contract', 'Employment Contract'),
        ('photo', 'Passport Photo'),
        ('bank_details', 'Bank Details'),
        ('medical', 'Medical Certificate'),
        ('other', 'Other'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=upload_to_path)
    description = models.TextField(blank=True)
    is_confidential = models.BooleanField(default=False)
    expiry_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.title}"
    
    @property
    def is_expired(self):
        if self.expiry_date:
            from datetime import date
            return date.today() > self.expiry_date
        return False
    
    class Meta:
        verbose_name = "Employee Document"
        verbose_name_plural = "Employee Documents"
        ordering = ['-created_at']

class Attendance(TimeStampedModel):
    """Employee attendance tracking"""
    
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('sick_leave', 'Sick Leave'),
        ('annual_leave', 'Annual Leave'),
        ('maternity_leave', 'Maternity Leave'),
        ('paternity_leave', 'Paternity Leave'),
        ('unpaid_leave', 'Unpaid Leave'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    break_duration = models.DurationField(null=True, blank=True)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_attendance'
    )
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.date} ({self.get_status_display()})"
    
    @property
    def hours_worked(self):
        if self.check_in_time and self.check_out_time:
            from datetime import datetime, timedelta
            check_in = datetime.combine(self.date, self.check_in_time)
            check_out = datetime.combine(self.date, self.check_out_time)
            
            if check_out < check_in:
                check_out += timedelta(days=1)
            
            worked = check_out - check_in
            if self.break_duration:
                worked -= self.break_duration
            
            return worked.total_seconds() / 3600
        return 0
    
    @property
    def is_late(self):
        if self.check_in_time and self.status == 'present':
            from datetime import time
            expected_time = time(8, 0)  # 8:00 AM default
            # TODO: Get from business settings
            return self.check_in_time > expected_time
        return False
    
    class Meta:
        verbose_name = "Attendance"
        verbose_name_plural = "Attendance Records"
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']

class Leave(TimeStampedModel):
    """Employee leave management"""
    
    LEAVE_TYPES = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('compassionate', 'Compassionate Leave'),
        ('study', 'Study Leave'),
        ('unpaid', 'Unpaid Leave'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.IntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    approved_by = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_leaves'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Supporting documents
    medical_certificate = models.FileField(upload_to='leave_documents/', blank=True, null=True)
    supporting_document = models.FileField(upload_to='leave_documents/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date.")
    
    class Meta:
        verbose_name = "Leave Request"
        verbose_name_plural = "Leave Requests"
        ordering = ['-created_at']

class PerformanceReview(TimeStampedModel):
    """Employee performance review"""
    
    REVIEW_TYPES = [
        ('probation', 'Probation Review'),
        ('annual', 'Annual Review'),
        ('quarterly', 'Quarterly Review'),
        ('project', 'Project Review'),
        ('disciplinary', 'Disciplinary Review'),
    ]
    
    RATING_CHOICES = [
        (1, 'Poor'),
        (2, 'Below Average'),
        (3, 'Average'),
        (4, 'Good'),
        (5, 'Excellent'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performance_reviews')
    reviewer = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='conducted_reviews'
    )
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPES)
    review_period_start = models.DateField()
    review_period_end = models.DateField()
    
    # Ratings
    quality_of_work = models.IntegerField(choices=RATING_CHOICES, default=3)
    punctuality = models.IntegerField(choices=RATING_CHOICES, default=3)
    teamwork = models.IntegerField(choices=RATING_CHOICES, default=3)
    communication = models.IntegerField(choices=RATING_CHOICES, default=3)
    initiative = models.IntegerField(choices=RATING_CHOICES, default=3)
    customer_service = models.IntegerField(choices=RATING_CHOICES, default=3)
    
    # Comments
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    goals_for_next_period = models.TextField(blank=True)
    additional_comments = models.TextField(blank=True)
    
    # Overall
    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, default=3.0)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    
    # Employee acknowledgment
    employee_acknowledged = models.BooleanField(default=False)
    employee_acknowledged_at = models.DateTimeField(null=True, blank=True)
    employee_comments = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.get_review_type_display()} ({self.review_period_start})"
    
    def save(self, *args, **kwargs):
        # Calculate overall rating
        ratings = [
            self.quality_of_work, self.punctuality, self.teamwork,
            self.communication, self.initiative, self.customer_service
        ]
        self.overall_rating = sum(ratings) / len(ratings)
        super().save(*args, **kwargs)
        
        # Update employee's performance rating
        self.employee.performance_rating = self.overall_rating
        self.employee.save(update_fields=['performance_rating'])
    
    class Meta:
        verbose_name = "Performance Review"
        verbose_name_plural = "Performance Reviews"
        ordering = ['-created_at']

class Training(TimeStampedModel):
    """Training programs and certifications"""
    
    TRAINING_TYPES = [
        ('onboarding', 'Onboarding'),
        ('safety', 'Safety Training'),
        ('technical', 'Technical Skills'),
        ('customer_service', 'Customer Service'),
        ('leadership', 'Leadership'),
        ('compliance', 'Compliance'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    training_type = models.CharField(max_length=20, choices=TRAINING_TYPES)
    trainer = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)
    
    # Schedule
    start_date = models.DateField()
    end_date = models.DateField()
    duration_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Participants
    employees = models.ManyToManyField(Employee, through='TrainingParticipant', related_name='trainings')
    
    # Materials
    materials = models.FileField(upload_to='training_materials/', blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Costs
    cost_per_participant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return self.title
    
    @property
    def participant_count(self):
        return self.participants.count()
    
    @property
    def total_cost(self):
        return self.cost_per_participant * self.participant_count
    
    class Meta:
        verbose_name = "Training"
        verbose_name_plural = "Training Programs"
        ordering = ['-start_date']

class TrainingParticipant(TimeStampedModel):
    """Training participation tracking"""
    
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('attended', 'Attended'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('absent', 'Absent'),
    ]
    
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='participants')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='training_participations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enrolled')
    
    # Results
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    certificate_issued = models.BooleanField(default=False)
    certificate_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    
    # Feedback
    feedback = models.TextField(blank=True)
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], 
        null=True, 
        blank=True
    )
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.training.title}"
    
    class Meta:
        verbose_name = "Training Participant"
        verbose_name_plural = "Training Participants"
        unique_together = ['training', 'employee']

class Payroll(TimeStampedModel):
    """Employee payroll records"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    pay_period_start = models.DateField()
    pay_period_end = models.DateField()
    
    # Basic Pay
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Allowances
    transport_allowance = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    meal_allowance = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    housing_allowance = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    other_allowances = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Deductions
    tax_deduction = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    nhif_deduction = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    nssf_deduction = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    advance_deduction = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Totals
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('cheque', 'Cheque'),
            ('mobile_money', 'Mobile Money'),
        ],
        default='bank_transfer'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.pay_period_start} to {self.pay_period_end}"
    
    def calculate_totals(self):
        """Calculate gross pay, total deductions, and net pay"""
        # Gross pay calculation
        basic_pay = self.basic_salary if self.basic_salary > 0 else (self.hourly_rate * self.hours_worked)
        overtime_pay = self.overtime_hours * self.overtime_rate
        allowances = (self.transport_allowance + self.meal_allowance + 
                     self.housing_allowance + self.other_allowances)
        
        self.gross_pay = basic_pay + overtime_pay + allowances + self.commission + self.bonus
        
        # Total deductions
        self.total_deductions = (self.tax_deduction + self.nhif_deduction + 
                               self.nssf_deduction + self.loan_deduction + 
                               self.advance_deduction + self.other_deductions)
        
        # Net pay
        self.net_pay = self.gross_pay - self.total_deductions
    
    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Payroll Record"
        verbose_name_plural = "Payroll Records"
        unique_together = ['employee', 'pay_period_start', 'pay_period_end']
        ordering = ['-pay_period_start']