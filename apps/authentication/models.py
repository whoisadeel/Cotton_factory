"""
Authentication Models - Custom User, Login Attempts, Audit Logs
"""
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model with additional fields for cotton factory.
    Built with RBAC groundwork even though we start with single user.
    """
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ur', 'Urdu'),
    ]

    ROLE_CHOICES = [
        ('owner', 'Owner / Admin'),
        ('manager', 'Manager'),
        ('accountant', 'Accountant'),
        ('data_entry', 'Data Entry Operator'),
        ('viewer', 'Viewer (Read Only)'),
    ]

    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', blank=True, null=True
    )
    preferred_language = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default='en'
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='owner'
    )
    security_question = models.CharField(max_length=255, blank=True)
    security_answer = models.CharField(max_length=255, blank=True)

    # Override groups and user_permissions with unique related_name
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.get_full_name() or self.username


class LoginAttempt(models.Model):
    """Track failed login attempts for lockout mechanism."""
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    was_successful = models.BooleanField(default=False)

    class Meta:
        db_table = 'login_attempts'
        ordering = ['-attempted_at']

    def __str__(self):
        status = 'Success' if self.was_successful else 'Failed'
        return f"{self.username} - {status} - {self.attempted_at}"

    @classmethod
    def get_recent_failures(cls, username, minutes=15):
        """Get count of recent failed login attempts."""
        cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
        return cls.objects.filter(
            username=username,
            was_successful=False,
            attempted_at__gte=cutoff
        ).count()

    @classmethod
    def is_locked_out(cls, username, max_attempts=5, lockout_minutes=15):
        """Check if a username is currently locked out."""
        return cls.get_recent_failures(username, lockout_minutes) >= max_attempts


class AuditLog(models.Model):
    """
    Immutable audit trail for all system actions.
    Cannot be deleted through the application.
    """
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('VIEW', 'Viewed'),
        ('EXPORT', 'Exported'),
        ('PRINT', 'Printed'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        # Prevent deletion at the model level
        managed = True

    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"

    def delete(self, *args, **kwargs):
        """Prevent deletion of audit logs."""
        raise PermissionError("Audit logs cannot be deleted.")

    @classmethod
    def log(cls, user, action, model_name='', object_id='',
            object_repr='', changes=None, request=None, description=''):
        """Create an audit log entry."""
        ip_address = None
        user_agent = ''
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        return cls.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id else '',
            object_repr=object_repr[:255] if object_repr else '',
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
        )

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
