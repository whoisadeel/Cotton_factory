from django.urls import path
from . import views

app_name = 'parties'

urlpatterns = [
    path('', views.party_list, name='party_list'),
    path('create/', views.party_create, name='party_create'),
    path('<int:pk>/', views.party_detail, name='party_detail'),
    path('<int:pk>/edit/', views.party_edit, name='party_edit'),
    path('<int:pk>/delete/', views.party_delete, name='party_delete'),
    path('api/search/', views.party_search_api, name='party_search_api'),
    path('api/<int:pk>/bank-info/', views.party_bank_info_api, name='party_bank_info_api'),
    path('api/quick-add/', views.party_quick_add_api, name='party_quick_add_api'),
]
