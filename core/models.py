import datetime
from io import BytesIO
from django.db import models
from django.utils import timezone
from django.core.files import File
import qrcode

class Service(models.Model):
    name = models.CharField(max_length=100)
    estimated_duration_minutes = models.IntegerField(default=15)
    
    def __str__(self):
        return self.name

class Counter(models.Model):
    name = models.CharField(max_length=50, help_text="e.g., Counter 1, Priority Counter")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class Appointment(models.Model):
    TYPE_CHOICES = (
        ('R', 'Regular'),
        ('P', 'Priority (Senior/PWD/Pregnant)'),
    )
    
    STATUS_CHOICES = (
        ('Waiting', 'Waiting in Queue'),
        ('Serving', 'Currently Serving'),
        ('Completed', 'Completed'),
        ('Missed', 'Missed/No-Show'),
    )

    customer_name = models.CharField(max_length=150)
    appointment_type = models.CharField(max_length=1, choices=TYPE_CHOICES, default='R')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Waiting')
    
    # Auto-generated fields
    queue_number = models.CharField(max_length=20, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    served_at = models.DateTimeField(blank=True, null=True)
    qr_code = models.ImageField(upload_to='qrcodes/', blank=True, null=True)
    assigned_counter = models.ForeignKey(Counter, on_delete=models.SET_NULL, blank=True, null=True)

    def save(self, *args, **kwargs):
        # 1. Generate Queue Number reliably based on today's latest ticket
        if not self.queue_number:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Fetch the latest appointment of this type created today
            latest_appt = Appointment.objects.filter(
                appointment_type=self.appointment_type,
                created_at__gte=today_start
            ).order_by('-id').first()

            if latest_appt and latest_appt.queue_number:
                try:
                    # Extract the sequence number from e.g. "R-001" -> 1
                    last_sequence = int(latest_appt.queue_number.split('-')[-1])
                    sequence = last_sequence + 1
                except (ValueError, IndexError):
                    sequence = 1
            else:
                sequence = 1

            self.queue_number = f"{self.appointment_type}-{sequence:03d}"

        # 2. Generate QR Code containing the queue number
        if not self.qr_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(f"VERIFY:{self.queue_number}")
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f'qr_{self.queue_number}.png'
            self.qr_code.save(file_name, File(buffer), save=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.queue_number}] {self.customer_name} - {self.status}"
