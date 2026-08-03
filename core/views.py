from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from .models import Appointment, Service, Counter
from .forms import AppointmentForm
from django.views.decorators.http import require_GET, require_POST
import json
from django.http import JsonResponse

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
    if new_status in ('Completed', 'Missed') and not appt.ended_at:
        appt.ended_at = timezone.now()
    appt.save()
    messages.success(request, f"Ticket [{appt.queue_number}] updated to {new_status}.")
    return redirect('dashboard')

@staff_member_required
@require_GET
def verify_view(request):
    return render(request, 'verify.html')


@staff_member_required
@require_POST
def verify_ticket_api(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        payload = {}

    raw_code = (payload.get('code') or '').strip()
    if not raw_code:
        return JsonResponse({'valid': False, 'reason': 'EMPTY'})

    # A scanned QR encodes "VERIFY:<queue_number>"; manual entry may just be the bare queue number.
    if raw_code.upper().startswith('VERIFY:'):
        queue_number = raw_code.split(':', 1)[1].strip()
    else:
        queue_number = raw_code

    try:
        appt = Appointment.objects.select_related('service').get(queue_number__iexact=queue_number)
    except Appointment.DoesNotExist:
        return JsonResponse({'valid': False, 'reason': 'NOT_FOUND', 'submitted_code': raw_code})

    already_checked_in = appt.checked_in_at is not None
    if not already_checked_in and appt.status not in ('Completed', 'Missed'):
        appt.checked_in_at = timezone.now()
        appt.save(update_fields=['checked_in_at'])

    return JsonResponse({
        'valid': True,
        'already_checked_in': already_checked_in,
        'queue_number': appt.queue_number,
        'customer_name': appt.customer_name,
        'service': appt.service.name,
        'appointment_type': appt.get_appointment_type_display(),
        'status': appt.status,
        'checked_in_at': timezone.localtime(appt.checked_in_at).strftime('%I:%M:%S %p') if appt.checked_in_at else '—',
    })

@staff_member_required
def performance_dashboard_view(request):
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    todays = list(
        Appointment.objects.filter(created_at__gte=today_start)
        .select_related('service', 'assigned_counter')
    )

    def avg_minutes(durations):
        if not durations:
            return None
        seconds = sum(d.total_seconds() for d in durations)
        return round((seconds / len(durations)) / 60, 1)

    completed = [a for a in todays if a.status == 'Completed']
    missed = [a for a in todays if a.status == 'Missed']
    resolved_count = len(completed) + len(missed)

    completion_rate = round((len(completed) / resolved_count) * 100, 1) if resolved_count else None
    no_show_rate = round((len(missed) / resolved_count) * 100, 1) if resolved_count else None

    avg_wait = avg_minutes([a.served_at - a.created_at for a in todays if a.served_at])
    avg_service_time = avg_minutes([a.ended_at - a.served_at for a in todays if a.served_at and a.ended_at])

    # Per-service breakdown, with a bar width normalized against the busiest service today
    all_services = list(Service.objects.all())
    service_counts = {s.id: sum(1 for a in todays if a.service_id == s.id) for s in all_services}
    max_service_count = max(service_counts.values(), default=0)
    service_stats = []
    for service in all_services:
        s_appts = [a for a in todays if a.service_id == service.id]
        count = len(s_appts)
        service_stats.append({
            'service': service,
            'count': count,
            'bar_pct': round((count / max_service_count) * 100) if max_service_count else 0,
            'avg_wait': avg_minutes([a.served_at - a.created_at for a in s_appts if a.served_at]),
            'avg_service_time': avg_minutes([a.ended_at - a.served_at for a in s_appts if a.served_at and a.ended_at]),
        })

    # Per-counter breakdown: throughput + average speed
    counter_stats = []
    for counter in Counter.objects.filter(is_active=True):
        c_resolved = [a for a in todays if a.assigned_counter_id == counter.id and a.status in ('Completed', 'Missed')]
        counter_stats.append({
            'counter': counter,
            'served_count': len(c_resolved),
            'avg_service_time': avg_minutes([a.ended_at - a.served_at for a in c_resolved if a.served_at and a.ended_at]),
        })

    # Regular vs Priority — shows whether the priority queue is actually cutting wait time
    type_stats = []
    for code, label in Appointment.TYPE_CHOICES:
        t_appts = [a for a in todays if a.appointment_type == code]
        type_stats.append({
            'label': label,
            'count': len(t_appts),
            'avg_wait': avg_minutes([a.served_at - a.created_at for a in t_appts if a.served_at]),
        })

    return render(request, 'performance.html', {
        'total_today': len(todays),
        'waiting_count': sum(1 for a in todays if a.status == 'Waiting'),
        'serving_count': sum(1 for a in todays if a.status == 'Serving'),
        'completed_count': len(completed),
        'missed_count': len(missed),
        'completion_rate': completion_rate,
        'no_show_rate': no_show_rate,
        'avg_wait': avg_wait,
        'avg_service_time': avg_service_time,
        'service_stats': service_stats,
        'counter_stats': counter_stats,
        'type_stats': type_stats,
    })