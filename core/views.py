from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from .models import Appointment, Service, Counter
from .forms import AppointmentForm
from django.views.decorators.http import require_GET

def booking_view(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            ticket = form.save()
            return redirect('ticket_detail', queue_number=ticket.queue_number)
        else:
            messages.error(request, "Form validation failed. Please select a valid service.")
    else:
        form = AppointmentForm()

    return render(request, 'booking.html', {
        'form': form, 
        'ticket': None, 
        'estimated_wait': 0
    })

@require_GET
def ticket_detail_view(request, queue_number):
    ticket = get_object_or_404(Appointment, queue_number=queue_number)
    
    waiting_ahead = Appointment.objects.filter(
        status='Waiting',
        created_at__lt=ticket.created_at
    ).count()
    estimated_wait = waiting_ahead * ticket.service.estimated_duration_minutes

    form = AppointmentForm()
    return render(request, 'booking.html', {
        'form': form,
        'ticket': ticket,
        'estimated_wait': estimated_wait
    })

def display_view(request):
    serving = Appointment.objects.filter(status='Serving').select_related('service', 'assigned_counter').order_by('-served_at')[:6]
    waiting = Appointment.objects.filter(status='Waiting').select_related('service').order_by('appointment_type', 'created_at')[:8]
    
    return render(request, 'display.html', {
        'serving': serving,
        'waiting': waiting
    })

@staff_member_required
def dashboard_view(request):
    # Ensure standard counters exist
    default_counters = ["Counter 1", "Counter 2", "Counter 3", "Priority Counter"]
    for name in default_counters:
        Counter.objects.get_or_create(name=name)

    counters = Counter.objects.filter(is_active=True)
    
    # Query current active ticket for EVERY counter
    counter_data = []
    for counter in counters:
        active_ticket = Appointment.objects.filter(status='Serving', assigned_counter=counter).first()
        counter_data.append({
            'counter': counter,
            'currently_serving': active_ticket
        })

    next_regular = Appointment.objects.filter(status='Waiting', appointment_type='R').order_by('created_at').first()
    next_priority = Appointment.objects.filter(status='Waiting', appointment_type='P').order_by('created_at').first()
    
    # Fetch recent appointments with service and counter relations
    recent_appointments = Appointment.objects.select_related('service', 'assigned_counter').order_by('-created_at')[:20]

    return render(request, 'dashboard.html', {
        'counter_data': counter_data,
        'next_regular': next_regular,
        'next_priority': next_priority,
        'recent_appointments': recent_appointments,
    })

@staff_member_required
def call_next_counter(request, counter_id, queue_type):
    counter = get_object_or_404(Counter, id=counter_id)

    # Safety Guardrail: Prevent overwriting active client on this specific desk
    active_ticket = Appointment.objects.filter(status='Serving', assigned_counter=counter).first()
    if active_ticket:
        messages.warning(
            request, 
            f"BLOCKED: {counter.name} is currently serving [{active_ticket.queue_number}]. Mark as 'COMPLETE' or 'NO-SHOW' first."
        )
        return redirect('dashboard')

    next_appt = Appointment.objects.filter(status='Waiting', appointment_type=queue_type).order_by('created_at').first()
    
    if next_appt:
        next_appt.status = 'Serving'
        next_appt.served_at = timezone.now()
        next_appt.assigned_counter = counter
        next_appt.save()
        messages.success(request, f"Called [{next_appt.queue_number}] to {counter.name}.")
    else:
        messages.info(request, f"No waiting tickets in the {'Priority' if queue_type == 'P' else 'Regular'} queue.")

    return redirect('dashboard')

@staff_member_required
def update_status(request, appt_id, new_status):
    appt = get_object_or_404(Appointment, id=appt_id)
    appt.status = new_status
    appt.save()
    messages.success(request, f"Ticket [{appt.queue_number}] updated to {new_status}.")
    return redirect('dashboard')