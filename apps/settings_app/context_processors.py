"""
Context processors — company settings + date presets for all templates.
"""
from .models import CompanySettings


def company_settings(request):
    """Add company settings to template context."""
    try:
        settings = CompanySettings.get_settings()
    except Exception:
        settings = None
    return {'company': settings}


def date_presets(request):
    """Add date filter presets to all templates — used by date_filter.html component."""
    from datetime import date, timedelta
    today = date.today()

    weekday = today.weekday()  # 0=Monday
    week_start = today - timedelta(days=weekday)
    month_start = today.replace(day=1)
    year_start = date(today.year, 1, 1)

    # Financial year (Pakistan: July–June)
    if today.month >= 7:
        fy_start = date(today.year, 7, 1)
    else:
        fy_start = date(today.year - 1, 7, 1)

    return {
        'today_iso': today.isoformat(),
        'week_start': week_start.isoformat(),
        'month_start': month_start.isoformat(),
        'year_start': year_start.isoformat(),
        'fy_start': fy_start.isoformat(),
    }
