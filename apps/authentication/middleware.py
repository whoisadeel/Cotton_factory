"""
Middleware — Session timeout, IP capture, and audit logging.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class SessionTimeoutMiddleware(MiddlewareMixin):
    """Auto-logout after inactivity."""
    def process_request(self, request):
        if not request.user.is_authenticated:
            return
        last_activity = request.session.get('last_activity')
        if last_activity:
            from datetime import datetime
            try:
                last = datetime.fromisoformat(last_activity)
                timeout = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 30)
                diff = (timezone.now() - timezone.make_aware(last) if timezone.is_naive(last) else timezone.now() - last)
                if diff.total_seconds() > timeout * 60:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/auth/login/?timeout=1')
            except (ValueError, TypeError):
                pass
        request.session['last_activity'] = timezone.now().isoformat()


class AuditLogMiddleware(MiddlewareMixin):
    """
    Captures client IP on every request so views can use request.client_ip.
    """
    def process_request(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            request.client_ip = x_forwarded.split(',')[0].strip()
        else:
            request.client_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
