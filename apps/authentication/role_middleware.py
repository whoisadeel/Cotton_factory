"""
Role-based access control middleware.
Admin (owner) — full access.
Accountant — can view everything, can create payments/receipts/expenses, 
             but CANNOT: delete/void purchases/sales, change settings, manage users.
"""
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.shortcuts import redirect


# URLs accountants are NOT allowed to access
ACCOUNTANT_BLOCKED = [
    '/settings/',
    '/auth/audit-log/',
    '/auth/login-history/',
]

# URL patterns accountants cannot POST to (destructive actions)
ACCOUNTANT_BLOCKED_POST = [
    '/delete/',
    '/void/',
    '/finalize/',  # only admin can finalize
]


class RoleAccessMiddleware:
    """Restrict access based on user role."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        role = getattr(request.user, 'role', 'owner')

        # Admin/owner — full access
        if role in ('owner', 'manager', ''):
            return self.get_response(request)

        # Accountant restrictions
        if role == 'accountant':
            path = request.path

            # Block certain pages entirely
            for blocked in ACCOUNTANT_BLOCKED:
                if path.startswith(blocked):
                    messages.error(request, 'Access restricted — صرف ایڈمن کے لیے')
                    return redirect('/dashboard/')

            # Block destructive POST actions
            if request.method == 'POST':
                for blocked in ACCOUNTANT_BLOCKED_POST:
                    if blocked in path:
                        messages.error(request, 'This action requires admin access — یہ عمل صرف ایڈمن کر سکتا ہے')
                        return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))

        # Data entry — read-only for finance, no access to settings
        if role == 'data_entry':
            path = request.path
            for blocked in ACCOUNTANT_BLOCKED:
                if path.startswith(blocked):
                    messages.error(request, 'Access restricted')
                    return redirect('/dashboard/')
            # Block all POST to finance/accounting
            if request.method == 'POST' and any(x in path for x in ['/finance/', '/accounting/']):
                messages.error(request, 'Finance access restricted — مالیاتی رسائی محدود ہے')
                return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))

        # Viewer — block all POST
        if role == 'viewer':
            if request.method == 'POST':
                messages.error(request, 'Read-only access — صرف دیکھنے کی اجازت')
                return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))

        return self.get_response(request)
