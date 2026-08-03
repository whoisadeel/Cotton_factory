"""
Product & Category Views
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.authentication.models import AuditLog
from .models import Category, Product, UnitOfMeasurement
from .forms import CategoryForm, ProductForm, UnitForm


# ─── PRODUCT VIEWS ──────────────────────────────────────────

@login_required
def product_list(request):
    """List all products with search and filter."""
    products = Product.objects.select_related('category', 'unit').all()

    # Search
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(name_urdu__icontains=search) |
            Q(code__icontains=search)
        )

    # Filter by category
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    # Filter by status
    status = request.GET.get('status')
    if status:
        products = products.filter(status=status)

    categories = Category.objects.filter(is_active=True)

    context = {
        'products': products,
        'categories': categories,
        'search': search,
        'selected_category': category_id,
        'selected_status': status,
    }

    if request.htmx:
        return render(request, 'products/partials/product_table.html', context)

    from django.core.paginator import Paginator
    paginator = Paginator(products, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    context['products'] = page_obj
    context['page_obj'] = page_obj
    return render(request, 'products/product_list.html', context)


@login_required
def product_create(request):
    """Create a new product."""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            AuditLog.log(
                user=request.user, action='CREATE',
                model_name='Product', object_id=product.pk,
                object_repr=str(product), request=request,
                description=f'Product created: {product.name}'
            )
            messages.success(request, f'Product "{product.name}" created successfully.')
            if request.htmx:
                return HttpResponse(status=204, headers={
                    'HX-Trigger': 'productChanged',
                    'HX-Redirect': '/products/',
                })
            return redirect('products:product_list')
    else:
        form = ProductForm()

    template = 'products/partials/product_form.html' if request.htmx else 'products/product_form.html'
    return render(request, template, {'form': form, 'title': 'Add New Product'})


@login_required
def product_edit(request, pk):
    """Edit an existing product."""
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            AuditLog.log(
                user=request.user, action='UPDATE',
                model_name='Product', object_id=product.pk,
                object_repr=str(product), request=request,
                changes=form.changed_data,
                description=f'Product updated: {product.name}'
            )
            messages.success(request, f'Product "{product.name}" updated successfully.')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': '/products/'})
            return redirect('products:product_list')
    else:
        form = ProductForm(instance=product)

    template = 'products/partials/product_form.html' if request.htmx else 'products/product_form.html'
    return render(request, template, {'form': form, 'product': product, 'title': f'Edit: {product.name}'})


@login_required
@require_POST
def product_delete(request, pk):
    """Soft-delete (deactivate) a product. POST only. System products cannot be deleted."""
    product = get_object_or_404(Product, pk=pk)
    if product.is_system:
        messages.error(request, 'System products cannot be deleted.')
    else:
        product.status = 'inactive'
        product.save()
        AuditLog.log(
            user=request.user, action='DELETE',
            model_name='Product', object_id=product.pk,
            object_repr=str(product), request=request,
            description=f'Product deactivated: {product.name}'
        )
        messages.success(request, f'Product "{product.name}" has been deactivated.')

    if request.htmx:
        return HttpResponse(status=204, headers={'HX-Trigger': 'productChanged'})
    return redirect('products:product_list')


# ─── CATEGORY VIEWS ──────────────────────────────────────────

@login_required
def category_list(request):
    """List all categories."""
    categories = Category.objects.all()
    search = request.GET.get('search', '')
    if search:
        categories = categories.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )

    context = {'categories': categories, 'search': search}
    if request.htmx:
        return render(request, 'products/partials/category_table.html', context)
    return render(request, 'products/category_list.html', context)


@login_required
def category_create(request):
    """Create a new category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            AuditLog.log(
                user=request.user, action='CREATE',
                model_name='Category', object_id=category.pk,
                object_repr=str(category), request=request
            )
            messages.success(request, f'Category "{category.name}" created.')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': '/products/categories/'})
            return redirect('products:category_list')
    else:
        form = CategoryForm()

    template = 'products/partials/category_form.html' if request.htmx else 'products/category_form.html'
    return render(request, template, {'form': form, 'title': 'Add Category'})


@login_required
def category_edit(request, pk):
    """Edit a category."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            AuditLog.log(
                user=request.user, action='UPDATE',
                model_name='Category', object_id=category.pk,
                object_repr=str(category), request=request
            )
            messages.success(request, f'Category "{category.name}" updated.')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': '/products/categories/'})
            return redirect('products:category_list')
    else:
        form = CategoryForm(instance=category)

    template = 'products/partials/category_form.html' if request.htmx else 'products/category_form.html'
    return render(request, template, {'form': form, 'category': category, 'title': f'Edit: {category.name}'})


# ─── UNIT VIEWS ──────────────────────────────────────────

@login_required
def unit_list(request):
    """List all units of measurement."""
    units = UnitOfMeasurement.objects.all()
    return render(request, 'products/unit_list.html', {'units': units})


@login_required
def unit_create(request):
    if request.method == 'POST':
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save()
            AuditLog.log(
                user=request.user, action='CREATE',
                model_name='UnitOfMeasurement', object_id=unit.pk,
                object_repr=str(unit), request=request
            )
            messages.success(request, f'Unit "{unit.name}" created.')
            return redirect('products:unit_list')
    else:
        form = UnitForm()
    return render(request, 'products/unit_form.html', {'form': form, 'title': 'Add Unit'})


@login_required
def unit_edit(request, pk):
    unit = get_object_or_404(UnitOfMeasurement, pk=pk)
    if request.method == 'POST':
        form = UnitForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            AuditLog.log(
                user=request.user, action='UPDATE',
                model_name='UnitOfMeasurement', object_id=unit.pk,
                object_repr=str(unit), request=request
            )
            messages.success(request, f'Unit "{unit.name}" updated.')
            return redirect('products:unit_list')
    else:
        form = UnitForm(instance=unit)
    return render(request, 'products/unit_form.html', {'form': form, 'unit': unit, 'title': f'Edit: {unit.name}'})


@login_required
def product_search_api(request):
    """API endpoint for product search (used in searchable dropdowns)."""
    from django.http import JsonResponse
    q = request.GET.get('q', '')
    products = Product.objects.filter(status='active')
    if q:
        products = products.filter(Q(name__icontains=q) | Q(code__icontains=q))
    products = products.select_related('category', 'unit')[:20]
    data = [{'id': p.pk, 'name': p.name, 'code': p.code, 'category': p.category.name,
             'unit': p.unit.abbreviation, 'purchase_price': str(p.default_purchase_price),
             'sale_price': str(p.default_sale_price), 'stock': str(p.current_stock)}
            for p in products]
    return JsonResponse(data, safe=False)


@login_required
@require_POST
def category_quick_add_api(request):
    """Quick-add a product category — returns JSON."""
    from django.http import JsonResponse
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required — نام ضروری ہے'}, status=400)

    # Generate a code from the name
    code = name.upper().replace(' ', '_')[:15]
    # Ensure unique
    from .models import Category
    base_code = code
    counter = 1
    while Category.objects.filter(code=code).exists():
        code = f"{base_code}_{counter}"
        counter += 1

    category = Category.objects.create(name=name, code=code)
    AuditLog.log(
        user=request.user, action='CREATE', model_name='Category',
        object_id=category.pk, object_repr=str(category), request=request,
        description=f'Quick-add category: {category.name}',
    )
    return JsonResponse({'id': category.pk, 'name': category.name, 'code': category.code})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    from apps.inventory.models import StockMovement
    movements = StockMovement.objects.filter(product=product).select_related('purchase', 'sale').order_by('-date')[:20]
    return render(request, 'products/product_detail.html', {
        'product': product, 'movements': movements,
    })
