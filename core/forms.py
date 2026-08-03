from django import forms
from .models import Appointment, Service

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['customer_name', 'service', 'appointment_type']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'ak-input w-full p-3 ak-clip-reverse',
                'placeholder': 'Enter client full name',
                'required': True
            }),
            'service': forms.Select(attrs={
                'class': 'ak-input w-full p-3 ak-clip-reverse',
                'required': True
            }),
            'appointment_type': forms.RadioSelect(attrs={
                'class': 'form-radio text-[#f5d000]'
            }),
        }