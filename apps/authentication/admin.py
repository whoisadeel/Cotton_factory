from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, LoginAttempt, AuditLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'preferred_language')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone', 'profile_picture', 'preferred_language', 'role',
                       'security_question', 'security_answer')
        }),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'was_successful', 'attempted_at')
    list_filter = ('was_successful', 'attempted_at')
    readonly_fields = ('username', 'ip_address', 'was_successful', 'attempted_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_repr', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'object_repr',
                       'changes', 'ip_address', 'user_agent', 'timestamp', 'description')

    def has_delete_permission(self, request, obj=None):
        return False
