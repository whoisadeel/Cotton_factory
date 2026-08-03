from django.urls import path
from . import views

app_name = 'transport'

urlpatterns = [
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('vehicles/create/', views.vehicle_create, name='vehicle_create'),
    path('vehicles/<int:pk>/', views.vehicle_detail, name='vehicle_detail'),
    path('vehicles/<int:pk>/edit/', views.vehicle_edit, name='vehicle_edit'),
    path('freight/', views.freight_list, name='freight_list'),
    path('freight/create/', views.freight_create, name='freight_create'),
    path('gate/', views.gate_entry_list, name='gate_entry_list'),
    path('gate/create/', views.gate_entry_create, name='gate_entry_create'),
    path('gate/<int:pk>/checkout/', views.gate_entry_checkout, name='gate_entry_checkout'),
]
