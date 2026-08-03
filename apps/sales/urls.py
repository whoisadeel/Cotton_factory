from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('create/', views.sale_create, name='sale_create'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/edit/', views.sale_edit, name='sale_edit'),
    path('<int:pk>/save-field/', views.sale_save_field, name='sale_save_field'),
    path('<int:pk>/add-item/', views.sale_add_item, name='sale_add_item'),
    path('<int:pk>/item/<int:item_pk>/save/', views.sale_save_item_field, name='sale_save_item_field'),
    path('<int:pk>/item/<int:item_pk>/delete/', views.sale_delete_item, name='sale_delete_item'),
    path('<int:pk>/finalize/', views.sale_finalize, name='sale_finalize'),
    path('<int:pk>/delete/', views.sale_delete, name='sale_delete'),
    # Returns
    path('returns/', views.sale_return_list, name='return_list'),
    path('returns/create/', views.sale_return_create, name='return_create'),
    path('returns/create/<int:sale_pk>/', views.sale_return_create, name='return_create_from'),
    path('cleanup-drafts/', views.sale_cleanup_drafts, name='cleanup_drafts'),
]
