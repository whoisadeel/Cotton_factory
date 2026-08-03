from django.urls import path
from . import views

app_name = 'settings_app'

urlpatterns = [
    path('', views.settings_view, name='index'),
    path('financial-years/', views.financial_year_list, name='financial_years'),
    path('financial-years/create/', views.financial_year_create, name='financial_year_create'),
    path('backup/', views.data_backup, name='backup'),
    path('import/', views.data_import, name='data_import'),
    path('export/', views.data_export, name='data_export'),
    path('test-backup-email/', views.test_backup_email, name='test_backup_email'),
    path('test-report-email/', views.test_report_email, name='test_report_email'),
]
