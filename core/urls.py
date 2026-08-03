from django.urls import path
from core import views

urlpatterns = [
    path('', views.booking_view, name='booking'),
    path('ticket/<str:queue_number>/', views.ticket_detail_view, name='ticket_detail'),
    path('display/', views.display_view, name='display'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/call/<int:counter_id>/<str:queue_type>/', views.call_next_counter, name='call_next_counter'),
    path('dashboard/status/<int:appt_id>/<str:new_status>/', views.update_status, name='update_status'),
    path('dashboard/verify/', views.verify_view, name='verify_ticket'),
    path('dashboard/verify/check/', views.verify_ticket_api, name='verify_ticket_api'),
    path('dashboard/performance/', views.performance_dashboard_view, name='performance_dashboard'),
    path('ticket/<str:queue_number>/feedback/', views.submit_feedback_view, name='submit_feedback'),
    path('qr/<str:queue_number>/', views.qr_code_view, name='qr_code'),
]