from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('update-security/', views.update_security_view, name='update_security'),
    path('audit-log/', views.audit_log_view, name='audit_log'),
    path('login-history/', views.login_history_view, name='login_history'),
]
