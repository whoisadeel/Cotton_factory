"""
Ginning Module Views — with proper form validation.
"""
from decimal import Decimal
from django.contrib import messages
from apps.authentication.models import AuditLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.products.models import Product
from .models import GinningLot, Bale
from .forms import GinningLotForm


@login_required
def lot_list(request):
    from django.db.models import Q
    from django.core.paginator import Paginator
    lots = GinningLot.objects.select_related('input_product', 'lint_product').all()
    search = request.GET.get('search', '')
    if search:
        lots = lots.filter(Q(lot_number__icontains=search))
    paginator = Paginator(lots, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'ginning/lot_list.html', {'lots': page_obj, 'search': search, 'page_obj': page_obj})


@login_required
def lot_create(request):
    if request.method == 'POST':
        form = GinningLotForm(request.POST)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.lot_number = GinningLot.generate_number()
            lot.created_by = request.user
            lot.save()
            AuditLog.log(user=request.user, action='CREATE', model_name='GinningLot',
                         object_id=lot.pk, object_repr=str(lot), request=request,
                         description=f'Ginning lot created: {lot.lot_number}')
            messages.success(request, f'Ginning lot {lot.lot_number} created.')
            return redirect('ginning:lot_edit', pk=lot.pk)
    else:
        form = GinningLotForm(initial={'date': timezone.now().date()})
    return render(request, 'ginning/lot_form.html', {'form': form, 'title': 'New Ginning Lot — نیا لاٹ', 'back_url': '/ginning/', 'submit_label': 'Create Lot', 'submit_label_ur': 'لاٹ بنائیں'})


@login_required
def lot_edit(request, pk):
    lot = get_object_or_404(GinningLot, pk=pk)
    if request.method == 'POST':
        lot.lint_product_id = request.POST.get('lint_product') or None
        lot.lint_quantity = Decimal(request.POST.get('lint_quantity') or '0')
        lot.seed_product_id = request.POST.get('seed_product') or None
        lot.seed_quantity = Decimal(request.POST.get('seed_quantity') or '0')
        lot.waste_product_id = request.POST.get('waste_product') or None
        lot.waste_quantity = Decimal(request.POST.get('waste_quantity') or '0')
        lot.electricity_cost = Decimal(request.POST.get('electricity_cost') or '0')
        lot.labour_cost = Decimal(request.POST.get('labour_cost') or '0')
        lot.maintenance_cost = Decimal(request.POST.get('maintenance_cost') or '0')
        lot.other_cost = Decimal(request.POST.get('other_cost') or '0')
        lot.calculate_got()
        lot.save()
        messages.success(request, f'Lot {lot.lot_number} updated. GOT: {lot.got_percentage}%')
        return redirect('ginning:lot_edit', pk=lot.pk)

    lint_products = Product.objects.filter(status='active', category__code='ROOI')
    seed_products = Product.objects.filter(status='active', category__code='BINOLA')
    waste_products = Product.objects.filter(status='active', category__code='JHAAR')
    return render(request, 'ginning/lot_edit.html', {
        'lot': lot, 'lint_products': lint_products, 'seed_products': seed_products,
        'waste_products': waste_products, 'bales': lot.bales.all(),
    })


@login_required
@require_POST
def lot_complete(request, pk):
    lot = get_object_or_404(GinningLot, pk=pk)
    lot.complete()
    AuditLog.log(user=request.user, action='UPDATE', model_name='GinningLot',
                 object_id=lot.pk, object_repr=str(lot), request=request,
                 description=f'Ginning lot completed: {lot.lot_number} — GOT: {lot.got_percentage}%')
    messages.success(request, f'Lot {lot.lot_number} completed! GOT: {lot.got_percentage}%')
    return redirect('ginning:lot_list')


@login_required
@require_POST
def bale_create(request, lot_pk):
    lot = get_object_or_404(GinningLot, pk=lot_pk)
    weight = Decimal(request.POST.get('weight') or '0')
    if weight <= 0:
        messages.error(request, 'Please enter bale weight.')
        return redirect('ginning:lot_edit', pk=lot.pk)
    existing = lot.bales.count()
    Bale.objects.create(
        bale_number=f"{lot.lot_number}-B{existing+1:03d}",
        ginning_lot=lot, weight=weight,
        grade=request.POST.get('grade', 'B'),
        storage_location=request.POST.get('storage_location', ''),
    )
    messages.success(request, f'Bale added ({weight} KG)')
    return redirect('ginning:lot_edit', pk=lot.pk)


@login_required
def bale_register(request):
    bales = Bale.objects.select_related('ginning_lot').all()
    return render(request, 'ginning/bale_register.html', {'bales': bales})
