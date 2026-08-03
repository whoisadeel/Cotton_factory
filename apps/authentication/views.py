"""
Authentication Views - Login, Logout, Profile, Password Management
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .forms import LoginForm, ProfileForm, CustomPasswordChangeForm, SecurityQuestionForm
from .models import LoginAttempt, AuditLog


def login_view(request):
    """Handle user login with lockout mechanism."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    timeout = request.GET.get('timeout')
    lockout_msg = None

    # Check brute force lockout — 5 failed attempts in 15 minutes
    if request.method == 'POST':
        from datetime import timedelta
        from django.utils import timezone
        ip = getattr(request, 'client_ip', '127.0.0.1')
        cutoff = timezone.now() - timedelta(minutes=15)
        recent_fails = LoginAttempt.objects.filter(
            ip_address=ip, was_successful=False, attempted_at__gte=cutoff
        ).count()
        if recent_fails >= 5:
            lockout_msg = '⚠️ Too many failed attempts. Please wait 15 minutes. — بہت زیادہ ناکام کوششیں۔ 15 منٹ انتظار کریں۔'

    if request.method == 'POST' and not lockout_msg:
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            remember_me = form.cleaned_data.get('remember_me', False)

            login(request, user)

            # Set session length based on remember me
            if remember_me:
                request.session.set_expiry(30 * 24 * 60 * 60)  # 30 days
            else:
                request.session.set_expiry(getattr(settings, 'SESSION_COOKIE_AGE', 1800))

            # Log successful login
            LoginAttempt.objects.create(
                username=user.username,
                ip_address=getattr(request, 'client_ip', '127.0.0.1'),
                was_successful=True
            )
            AuditLog.log(
                user=user,
                action='LOGIN',
                description='User logged in successfully',
                request=request
            )

            return redirect('dashboard:index')
        else:
            # Log failed attempt
            username = request.POST.get('username', '')
            if username:
                LoginAttempt.objects.create(
                    username=username,
                    ip_address=getattr(request, 'client_ip', '127.0.0.1'),
                    was_successful=False
                )
                AuditLog.log(
                    user=None,
                    action='LOGIN_FAILED',
                    description=f'Failed login attempt for username: {username}',
                    request=request
                )
    elif lockout_msg:
        form = LoginForm()
    else:
        form = LoginForm()

    return render(request, 'authentication/login.html', {
        'form': form,
        'timeout': timeout,
        'lockout_msg': lockout_msg,
    })


@login_required
@require_POST
def logout_view(request):
    """Handle user logout. POST only to prevent CSRF logout attacks."""
    AuditLog.log(
        user=request.user,
        action='LOGOUT',
        description='User logged out',
        request=request
    )
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('authentication:login')


@login_required
def profile_view(request):
    """View and update user profile."""
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            AuditLog.log(
                user=request.user,
                action='UPDATE',
                model_name='User',
                object_id=request.user.pk,
                object_repr=str(request.user),
                description='Profile updated',
                request=request
            )
            messages.success(request, 'Profile updated successfully.')
            if request.htmx:
                return render(request, 'authentication/partials/profile_form.html', {
                    'form': form,
                    'success': True,
                })
            return redirect('authentication:profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'authentication/profile.html', {
        'form': form,
        'password_form': CustomPasswordChangeForm(request.user),
        'security_form': SecurityQuestionForm(instance=request.user),
    })


@login_required
@require_POST
def change_password_view(request):
    """Handle password change."""
    form = CustomPasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        AuditLog.log(
            user=request.user,
            action='UPDATE',
            model_name='User',
            object_id=request.user.pk,
            description='Password changed',
            request=request
        )
        messages.success(request, 'Password changed successfully.')
        return redirect('authentication:profile')
    else:
        messages.error(request, 'Please correct the errors below.')
        return render(request, 'authentication/profile.html', {
            'form': ProfileForm(instance=request.user),
            'password_form': form,
            'security_form': SecurityQuestionForm(instance=request.user),
            'show_password_tab': True,
        })


@login_required
@require_POST
def update_security_view(request):
    """Update security question and answer."""
    form = SecurityQuestionForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        AuditLog.log(
            user=request.user,
            action='UPDATE',
            model_name='User',
            object_id=request.user.pk,
            description='Security question updated',
            request=request
        )
        messages.success(request, 'Security question updated successfully.')
    else:
        messages.error(request, 'Please correct the errors below.')
    return redirect('authentication:profile')


@login_required
def audit_log_view(request):
    """View all audit logs with filtering."""
    from django.core.paginator import Paginator
    logs = AuditLog.objects.select_related('user').all()

    # Filters
    action = request.GET.get('action', '')
    model = request.GET.get('model', '')
    user_id = request.GET.get('user', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if action:
        logs = logs.filter(action=action)
    if model:
        logs = logs.filter(model_name=model)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if search:
        from django.db.models import Q
        logs = logs.filter(
            Q(description__icontains=search) |
            Q(object_repr__icontains=search) |
            Q(model_name__icontains=search)
        )
    if date_from and date_to:
        logs = logs.filter(timestamp__date__range=[date_from, date_to])
    elif date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    elif date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Get unique values for filter dropdowns
    actions = AuditLog.ACTION_CHOICES
    models_used = AuditLog.objects.values_list('model_name', flat=True).distinct().order_by('model_name')
    from .models import User
    users = User.objects.filter(is_active=True).order_by('username')

    return render(request, 'authentication/audit_log.html', {
        'logs': page_obj, 'page_obj': page_obj,
        'actions': actions, 'models_used': models_used, 'users': users,
        'selected_action': action, 'selected_model': model,
        'selected_user': user_id, 'search': search,
        'filter_from': date_from, 'filter_to': date_to,
    })


@login_required
def login_history_view(request):
    """View login attempt history."""
    from django.core.paginator import Paginator
    attempts = LoginAttempt.objects.all()

    status_filter = request.GET.get('status', '')
    if status_filter == 'success':
        attempts = attempts.filter(was_successful=True)
    elif status_filter == 'failed':
        attempts = attempts.filter(was_successful=False)

    paginator = Paginator(attempts, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Stats
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    total = LoginAttempt.objects.count()
    successful = LoginAttempt.objects.filter(was_successful=True).count()
    failed = LoginAttempt.objects.filter(was_successful=False).count()
    recent_failed = LoginAttempt.objects.filter(
        was_successful=False, attempted_at__date__gte=week_ago
    ).count()

    return render(request, 'authentication/login_history.html', {
        'attempts': page_obj, 'page_obj': page_obj,
        'selected_status': status_filter,
        'total': total, 'successful': successful,
        'failed': failed, 'recent_failed': recent_failed,
    })
