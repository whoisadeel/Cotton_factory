"""
Custom template tags for smart form rendering.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='get_label')
def get_label(fields_dict, field_name):
    """Get the label for a form field by name."""
    try:
        field = fields_dict[field_name]
        return field.label or field_name.replace('_', ' ').title()
    except (KeyError, AttributeError):
        return field_name.replace('_', ' ').title()


@register.simple_tag
def render_field(field, colspan=''):
    """Render a form field with smart error display, inline."""
    urdu = getattr(field.field, 'urdu_label', '')
    has_errors = bool(field.errors)
    required = field.field.required

    col_class = ''
    if colspan == '2':
        col_class = ' sm:col-span-2'
    elif colspan == '3':
        col_class = ' sm:col-span-3'
    elif colspan == 'full':
        col_class = ' col-span-full'

    label_color = 'text-red-600' if has_errors else 'text-gray-700'
    urdu_color = 'text-red-400' if has_errors else 'text-gray-400'

    html = f'<div class="{col_class}">'

    # Label
    if field.label:
        html += f'<label for="{field.id_for_label}" class="flex items-baseline gap-1.5 mb-1.5 text-sm font-semibold {label_color}">'
        html += f'<span>{field.label}</span>'
        if urdu:
            html += f'<span class="text-xs font-normal {urdu_color}">({urdu})</span>'
        if required:
            html += '<span class="text-red-400 text-xs">*</span>'
        html += '</label>'

    # Field widget
    html += str(field)

    # Errors
    if has_errors:
        html += '<div class="mt-1.5 flex items-start gap-1.5" style="animation: slideDown 0.2s ease-out;">'
        html += '<svg class="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">'
        html += '<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>'
        html += '</svg><div>'
        for error in field.errors:
            html += f'<p class="text-sm font-medium text-red-600">{error}</p>'
        html += '</div></div>'
    elif field.help_text:
        html += f'<p class="mt-1 text-xs text-gray-400">{field.help_text}</p>'

    html += '</div>'
    return mark_safe(html)


@register.filter(name='split')
def split_filter(value, delimiter=','):
    """Split a string by delimiter."""
    if not value:
        return []
    return value.split(delimiter)
