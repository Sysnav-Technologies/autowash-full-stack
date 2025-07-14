from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={'class': css_class})

# Status classes for different order statuses
@register.filter(name='status_class')
def status_class(status):   
    status_classes = {
        'pending': 'badge badge-warning',
        'approved': 'badge badge-success',
        'rejected': 'badge badge-danger',
        'completed': 'badge badge-info',
    }
    return status_classes.get(status, 'badge badge-secondary')