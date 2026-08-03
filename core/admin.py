from django.contrib import admin
from .models import Service, Counter, Appointment

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'estimated_duration_minutes')

@admin.register(Counter)
class CounterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('queue_number', 'customer_name', 'service', 'appointment_type', 'status', 'created_at')
    list_filter = ('service', 'status', 'appointment_type', 'created_at')
    search_fields = ('queue_number', 'customer_name')
    readonly_fields = ('queue_number', 'qr_code', 'created_at', 'served_at')
