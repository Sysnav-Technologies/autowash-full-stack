"""
Shift Management Utilities
Handles shift status checking, validation, and business logic
"""
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from apps.businesses.models import Shift, ShiftAttendance


class ShiftManager:
    """Centralized shift management system"""
    
    @staticmethod
    def check_active_shifts():
        """Check for active shifts across all tenants"""
        return Shift.objects.filter(status='active')
    
    @staticmethod
    def can_start_new_shift(attendant=None):
        """Check if a new shift can be started"""
        active_shifts = Shift.objects.filter(status='active')
        
        if attendant:
            # Check if attendant has an active shift
            attendant_active_shift = active_shifts.filter(
                attendance_records__attendant=attendant
            ).exists()
            return not attendant_active_shift
        
        # Check if any shift is active
        return not active_shifts.exists()
    
    @staticmethod
    def get_attendant_current_shift(attendant):
        """Get attendant's current active shift"""
        try:
            return Shift.objects.filter(
                attendance_records__attendant=attendant,
                status='active'
            ).first()
        except Exception:
            return None
    
    @staticmethod
    def get_shift_status(attendant):
        """Get comprehensive shift status for an attendant"""
        current_shift = ShiftManager.get_attendant_current_shift(attendant)
        
        if not current_shift:
            return {
                'has_active_shift': False,
                'current_shift': None,
                'attendance_record': None,
                'can_start_shift': ShiftManager.can_start_new_shift(attendant),
                'status': 'no_shift'
            }
        
        # Get attendance record
        attendance_record = ShiftAttendance.objects.filter(
            shift=current_shift,
            attendant=attendant
        ).first()
        
        return {
            'has_active_shift': True,
            'current_shift': current_shift,
            'attendance_record': attendance_record,
            'can_start_shift': False,
            'status': 'active_shift'
        }
    
    @staticmethod
    def get_shift_statistics(attendant, date_range='today'):
        """Get shift statistics for an attendant"""
        from django.db.models import Sum, Avg, Count
        from decimal import Decimal
        
        today = timezone.now().date()
        
        if date_range == 'today':
            start_date = today
            end_date = today
        elif date_range == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif date_range == 'month':
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = today
            end_date = today
        
        # Get shifts in date range
        shifts = Shift.objects.filter(
            attendance_records__attendant=attendant,
            date__gte=start_date,
            date__lte=end_date
        ).distinct()
        
        # Calculate statistics
        total_shifts = shifts.count()
        completed_shifts = shifts.filter(status='completed').count()
        
        # Calculate total hours worked
        total_hours = Decimal('0')
        total_earnings = Decimal('0')
        
        for shift in shifts:
            attendance = ShiftAttendance.objects.filter(
                shift=shift,
                attendant=attendant
            ).first()
            
            if attendance:
                if attendance.check_out_time:
                    duration = attendance.check_out_time - attendance.check_in_time
                    hours = Decimal(str(duration.total_seconds() / 3600))
                    total_hours += hours
                    
                    # Calculate earnings (basic wage calculation)
                    if hasattr(attendant, 'hourly_wage') and attendant.hourly_wage:
                        total_earnings += hours * attendant.hourly_wage
        
        return {
            'total_shifts': total_shifts,
            'completed_shifts': completed_shifts,
            'total_hours': total_hours,
            'average_hours': total_hours / total_shifts if total_shifts > 0 else Decimal('0'),
            'total_earnings': total_earnings,
            'date_range': date_range
        }
    
    @staticmethod
    def get_team_shift_status():
        """Get shift status for all team members"""
        from apps.employees.models import Employee
        
        active_employees = Employee.objects.filter(
            is_active=True,
            role__in=['attendant', 'supervisor', 'manager']
        )
        
        team_status = []
        for employee in active_employees:
            status = ShiftManager.get_shift_status(employee)
            status['employee'] = employee
            team_status.append(status)
        
        return team_status
    
    @staticmethod
    def validate_shift_operation(operation, attendant, shift=None):
        """Validate shift operations (start, end, check-in, check-out)"""
        current_status = ShiftManager.get_shift_status(attendant)
        
        if operation == 'start_shift':
            if current_status['has_active_shift']:
                return False, "Cannot start new shift: You already have an active shift"
            
            if not ShiftManager.can_start_new_shift():
                return False, "Cannot start new shift: Another shift is currently active"
            
            return True, "Can start new shift"
        
        elif operation == 'end_shift':
            if not current_status['has_active_shift']:
                return False, "No active shift to end"
            
            return True, "Can end shift"
        
        elif operation == 'check_in':
            if not current_status['has_active_shift']:
                return False, "No active shift to check into"
            
            if current_status['attendance_record'] and current_status['attendance_record'].check_in_time:
                return False, "Already checked in to this shift"
            
            return True, "Can check in"
        
        elif operation == 'check_out':
            if not current_status['has_active_shift']:
                return False, "No active shift to check out from"
            
            attendance = current_status['attendance_record']
            if not attendance or not attendance.check_in_time:
                return False, "Must check in before checking out"
            
            if attendance.check_out_time:
                return False, "Already checked out"
            
            return True, "Can check out"
        
        return False, "Invalid operation"


def get_shift_context(request):
    """Context processor for shift-related data"""
    if not hasattr(request, 'employee') or not request.employee:
        return {}
    
    shift_status = ShiftManager.get_shift_status(request.employee)
    
    # Get today's statistics
    today_stats = ShiftManager.get_shift_statistics(request.employee, 'today')
    week_stats = ShiftManager.get_shift_statistics(request.employee, 'week')
    
    return {
        'shift_status': shift_status,
        'today_shift_stats': today_stats,
        'week_shift_stats': week_stats,
        'active_shifts_count': Shift.objects.filter(status='active').count(),
    }
