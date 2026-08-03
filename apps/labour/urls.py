from django.urls import path
from . import views

app_name = 'labour'

urlpatterns = [
    path('', views.worker_list, name='worker_list'),
    path('create/', views.worker_create, name='worker_create'),
    path('<int:pk>/edit/', views.worker_edit, name='worker_edit'),
    path('<int:pk>/', views.worker_detail, name='worker_detail'),
    path('attendance/', views.attendance_page, name='attendance'),
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/create/', views.payment_create, name='payment_create'),
    path('advances/create/', views.advance_create, name='advance_create'),
    path('api/attendance-summary/<int:worker_pk>/', views.attendance_summary_api, name='attendance_summary'),
]
