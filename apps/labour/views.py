"""
Labour Management Views — Workers, Attendance, Wages — with proper form validation.
"""
from decimal import Decimal
from django.contrib import messages
from apps.authentication.models import AuditLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Worker, Attendance, WorkerPayment, WorkerAdvance
from .forms import WorkerForm, WorkerPaymentForm


@login_required
def worker_list(request):
    from django.db.models import Q
    from django.core.paginator import Paginator
    workers = Worker.objects.all()
    search = request.GET.get('search', '')
    if search:
        workers = workers.filter(Q(name__icontains=search) | Q(phone__icontains=search) | Q(cnic__icontains=search))
    paginator = Paginator(workers, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'labour/worker_list.html', {'workers': page_obj, 'search': search, 'page_obj': page_obj})


@login_required
def worker_create(request):
    if request.method == 'POST':
        form = WorkerForm(request.POST)
        if form.is_valid():
            worker = form.save()
            AuditLog.log(user=request.user, action='CREATE', model_name='Worker',
                         object_id=worker.pk, object_repr=str(worker), request=request)
            messages.success(request, 'Worker added.')
            return redirect('labour:worker_list')
    else:
        form = WorkerForm()
    return render(request, 'labour/worker_form.html', {'form': form, 'title': 'Add Worker — مزدور شامل کریں', 'back_url': '/labour/', 'submit_label': 'Save', 'submit_label_ur': 'محفوظ کریں'})


@login_required
def attendance_page(request):
    day = request.GET.get('date')
    try:
        day = timezone.datetime.strptime(day, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        day = timezone.now().date()

    workers = Worker.objects.filter(is_active=True)
    existing = {a.worker_id: a for a in Attendance.objects.filter(date=day)}

    if request.method == 'POST':
        for w in workers:
            status = request.POST.get(f'status_{w.pk}', 'absent')
            ot = request.POST.get(f'overtime_{w.pk}', '0') or '0'
            Attendance.objects.update_or_create(
                worker=w, date=day,
                defaults={'status': status, 'overtime_hours': Decimal(ot)}
            )
        messages.success(request, f'Attendance saved for {day.strftime("%d/%m/%Y")}')
        return redirect(f'/labour/attendance/?date={day.isoformat()}')

    data = [{'worker': w, 'status': existing.get(w.pk, Attendance()).status or '', 'overtime': existing.get(w.pk, Attendance()).overtime_hours if w.pk in existing else 0} for w in workers]
    return render(request, 'labour/attendance.html', {'day': day, 'data': data, 'statuses': Attendance.STATUS_CHOICES})


@login_required
def payment_list(request):
    payments = WorkerPayment.objects.select_related('worker').all()[:100]
    return render(request, 'labour/payment_list.html', {'payments': payments})


@login_required
def payment_create(request):
    if request.method == 'POST':
        form = WorkerPaymentForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, f'Payment ₨{obj.net_amount:,.0f} to {obj.worker.name} recorded.')
            return redirect('labour:payment_list')
    else:
        form = WorkerPaymentForm(initial={'date': timezone.now().date()})
    return render(request, 'labour/payment_form.html', {'form': form, 'title': 'Worker Payment — مزدور ادائیگی', 'back_url': '/labour/payments/', 'submit_label': 'Save', 'submit_label_ur': 'محفوظ کریں'})


# ─── WORKER EDIT & DETAIL ─────────────────
@login_required
def worker_edit(request, pk):
    from .forms import WorkerForm
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == 'POST':
        form = WorkerForm(request.POST, instance=worker)
        if form.is_valid():
            form.save()
            AuditLog.log(user=request.user, action='UPDATE', model_name='Worker',
                         object_id=worker.pk, object_repr=str(worker), request=request)
            messages.success(request, f'Worker {worker.name} updated.')
            return redirect('labour:worker_list')
    else:
        form = WorkerForm(instance=worker)
    return render(request, 'labour/worker_form.html', {
        'form': form, 'title': f'Edit: {worker.name}',
        'back_url': '/labour/', 'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ'
    })


@login_required
def worker_detail(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    payments = WorkerPayment.objects.filter(worker=worker).order_by('-date')[:20]
    advances = WorkerAdvance.objects.filter(worker=worker).order_by('-date')[:20]
    attendance_recent = Attendance.objects.filter(worker=worker).order_by('-date')[:30]
    return render(request, 'labour/worker_detail.html', {
        'worker': worker, 'payments': payments, 'advances': advances, 'attendance': attendance_recent
    })


@login_required
def advance_create(request):
    if request.method == 'POST':
        worker_id = request.POST.get('worker', '').strip()
        amount = request.POST.get('amount', '').strip()

        if not worker_id:
            messages.error(request, 'Please select a worker — مزدور منتخب کریں')
        elif not amount or float(amount or 0) <= 0:
            messages.error(request, 'Amount must be greater than zero — رقم صفر سے زیادہ ہونی چاہیے')
        else:
            adv = WorkerAdvance.objects.create(
                worker_id=worker_id,
                date=request.POST.get('date') or timezone.now().date(),
                amount=amount,
                narration=request.POST.get('narration', ''),
            )
            AuditLog.log(user=request.user, action='CREATE', model_name='Advance',
                         object_id=adv.pk, object_repr=str(adv), request=request)
            messages.success(request, 'Advance recorded — پیشگی درج ہو گئی')
            return redirect('labour:worker_list')
    workers = Worker.objects.filter(is_active=True)
    return render(request, 'labour/advance_form.html', {
        'workers': workers, 'title': 'Worker Advance — پیشگی',
        'back_url': '/labour/', 'submit_label': 'Save', 'submit_label_ur': 'محفوظ'
    })



@login_required
def attendance_summary_api(request, worker_pk):
    """Return attendance summary for a worker for the current month."""
    from django.http import JsonResponse
    from datetime import date
    worker = get_object_or_404(Worker, pk=worker_pk)
    today = date.today()
    month_start = today.replace(day=1)
    att = Attendance.objects.filter(worker=worker, date__gte=month_start, date__lte=today)
    present = att.filter(status='present').count()
    absent = att.filter(status='absent').count()
    half_day = att.filter(status='half_day').count()
    leave = att.filter(status='leave').count()
    from django.db.models import Sum
    ot_hours = att.aggregate(t=Sum('overtime_hours'))['t'] or 0
    pending_advances = WorkerAdvance.objects.filter(worker=worker, is_recovered=False).aggregate(t=Sum('amount'))['t'] or 0
    return JsonResponse({
        'worker': worker.name, 'wage': float(worker.daily_wage),
        'present': present, 'absent': absent, 'half_day': half_day, 'leave': leave,
        'overtime_hours': float(ot_hours), 'pending_advances': float(pending_advances),
        'total_days': present + half_day,  # half days count as 0.5 but simplify to count
    })
