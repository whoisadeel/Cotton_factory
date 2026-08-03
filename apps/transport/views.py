"""
Transport & Gate Entry Views — with proper form validation.
"""
from django.contrib import messages
from apps.authentication.models import AuditLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Vehicle, FreightEntry, GateEntry
from .forms import VehicleForm, FreightForm, GateEntryForm


@login_required
def vehicle_list(request):
    from django.db.models import Q
    from django.core.paginator import Paginator
    vehicles = Vehicle.objects.select_related('owner').all()
    search = request.GET.get('search', '')
    if search:
        vehicles = vehicles.filter(Q(vehicle_number__icontains=search) | Q(driver_name__icontains=search))
    paginator = Paginator(vehicles, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'transport/vehicle_list.html', {'vehicles': page_obj, 'search': search, 'page_obj': page_obj})


@login_required
def vehicle_create(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save()
            AuditLog.log(user=request.user, action='CREATE', model_name='Vehicle',
                         object_id=vehicle.pk, object_repr=str(vehicle), request=request)
            messages.success(request, 'Vehicle added.')
            return redirect('transport:vehicle_list')
    else:
        form = VehicleForm()
    return render(request, 'transport/vehicle_form.html', {
        'form': form, 'title': 'Add Vehicle — گاڑی شامل کریں',
        'back_url': '/transport/vehicles/',
        'submit_label': 'Save', 'submit_label_ur': 'محفوظ کریں',
    })


@login_required
def freight_list(request):
    entries = FreightEntry.objects.select_related('vehicle', 'transporter').all()[:100]
    return render(request, 'transport/freight_list.html', {'entries': entries})


@login_required
def freight_create(request):
    if request.method == 'POST':
        form = FreightForm(request.POST)
        if form.is_valid():
            freight = form.save()
            AuditLog.log(user=request.user, action='CREATE', model_name='Freight',
                         object_id=freight.pk, object_repr=str(freight), request=request)
            messages.success(request, 'Freight entry added.')
            return redirect('transport:freight_list')
    else:
        form = FreightForm(initial={'date': timezone.now().date()})
    return render(request, 'transport/freight_form.html', {
        'form': form, 'title': 'Add Freight — بھاڑا',
        'back_url': '/transport/freight/',
        'submit_label': 'Save', 'submit_label_ur': 'محفوظ کریں',
    })


@login_required
def gate_entry_list(request):
    entries = GateEntry.objects.all()[:100]
    return render(request, 'transport/gate_entry_list.html', {'entries': entries})


@login_required
def gate_entry_create(request):
    if request.method == 'POST':
        form = GateEntryForm(request.POST)
        if form.is_valid():
            entry = form.save()
            AuditLog.log(user=request.user, action='CREATE', model_name='GateEntry',
                         object_id=entry.pk, object_repr=str(entry), request=request)
            messages.success(request, 'Gate entry recorded.')
            return redirect('transport:gate_entry_list')
    else:
        form = GateEntryForm()
    return render(request, 'transport/gate_entry_form.html', {
        'form': form, 'title': 'Gate Entry — گیٹ اندراج',
        'back_url': '/transport/gate/',
        'submit_label': 'Save', 'submit_label_ur': 'محفوظ کریں',
    })


# ─── EDIT VIEWS ─────────────────
@login_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            vehicle = form.save()
            AuditLog.log(user=request.user, action='UPDATE', model_name='Vehicle',
                         object_id=vehicle.pk, object_repr=str(vehicle), request=request)
            messages.success(request, 'Vehicle updated.')
            return redirect('transport:vehicle_list')
    else:
        form = VehicleForm(instance=vehicle)
    return render(request, 'transport/vehicle_form.html', {
        'form': form, 'title': f'Edit: {vehicle.vehicle_number}',
        'back_url': '/transport/vehicles/',
        'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ',
    })


@login_required
@require_POST
def gate_entry_checkout(request, pk):
    entry = get_object_or_404(GateEntry, pk=pk)
    entry.time_out = timezone.now()
    entry.save()
    messages.success(request, f'Vehicle {entry.vehicle_number} checked out.')
    return redirect('transport:gate_entry_list')


@login_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle.objects.select_related('owner'), pk=pk)
    from .models import FreightEntry
    freight = FreightEntry.objects.filter(vehicle=vehicle).order_by('-date')[:10]
    return render(request, 'transport/vehicle_detail.html', {
        'vehicle': vehicle, 'freight_entries': freight,
    })
