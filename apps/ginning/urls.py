from django.urls import path
from . import views
app_name = 'ginning'
urlpatterns = [
    path('', views.lot_list, name='lot_list'),
    path('create/', views.lot_create, name='lot_create'),
    path('<int:pk>/edit/', views.lot_edit, name='lot_edit'),
    path('<int:pk>/complete/', views.lot_complete, name='lot_complete'),
    path('<int:lot_pk>/bale/create/', views.bale_create, name='bale_create'),
    path('bales/', views.bale_register, name='bale_register'),
]
