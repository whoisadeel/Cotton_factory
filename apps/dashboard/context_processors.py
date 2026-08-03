"""
Context processor: injects date presets into every template.
"""
from datetime import date, timedelta


def date_presets(request):
    """Compute all date filter presets server-side so templates can use them reliably."""
    today = date.today()

    # This week (Monday start)
    weekday = today.weekday()  # 0=Monday
    week_start = today - timedelta(days=weekday)

    # This month
    month_start = today.replace(day=1)

    # This year
    year_start = today.replace(month=1, day=1)

    # Financial year (July–June)
    if today.month >= 7:
        fy_start = today.replace(month=7, day=1)
    else:
        fy_start = today.replace(year=today.year - 1, month=7, day=1)

    # Last 7 days
    last_7 = today - timedelta(days=7)
    # Last 30 days
    last_30 = today - timedelta(days=30)

    return {
        'DATE_TODAY': today.isoformat(),
        'DATE_WEEK_START': week_start.isoformat(),
        'DATE_MONTH_START': month_start.isoformat(),
        'DATE_YEAR_START': year_start.isoformat(),
        'DATE_FY_START': fy_start.isoformat(),
        'DATE_LAST_7': last_7.isoformat(),
        'DATE_LAST_30': last_30.isoformat(),
    }
