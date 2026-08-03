from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='purchase_list'),
    path('create/', views.purchase_create, name='purchase_create'),
    path('<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('<int:pk>/edit/', views.purchase_edit, name='purchase_edit'),
    path('<int:pk>/save-field/', views.purchase_save_field, name='purchase_save_field'),
    path('<int:pk>/add-item/', views.purchase_add_item, name='purchase_add_item'),
    path('<int:pk>/item/<int:item_pk>/save/', views.purchase_save_item_field, name='purchase_save_item_field'),
    path('<int:pk>/item/<int:item_pk>/delete/', views.purchase_delete_item, name='purchase_delete_item'),
    path('<int:pk>/finalize/', views.purchase_finalize, name='purchase_finalize'),
    path('<int:pk>/delete/', views.purchase_delete, name='purchase_delete'),
    # Returns
    path('returns/', views.purchase_return_list, name='return_list'),
    path('returns/create/', views.purchase_return_create, name='return_create'),
    path('returns/create/<int:purchase_pk>/', views.purchase_return_create, name='return_create_from'),
    path('cleanup-drafts/', views.purchase_cleanup_drafts, name='cleanup_drafts'),
]
