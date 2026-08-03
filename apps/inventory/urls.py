from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_overview, name='stock_overview'),
    path('movements/', views.stock_movements, name='stock_movements'),
    path('adjustment/', views.stock_adjustment, name='stock_adjustment'),
]
