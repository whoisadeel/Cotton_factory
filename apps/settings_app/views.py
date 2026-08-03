from django.contrib import messages
from apps.authentication.models import AuditLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from .models import CompanySettings


@login_required
def settings_view(request):
    settings_obj = CompanySettings.get_settings()
    if request.method == 'POST':
        # Update settings from form
        for field in ['company_name', 'company_name_urdu', 'address', 'city',
                      'district', 'province', 'country', 'phone', 'email',
                      'website', 'ntn_number', 'sales_tax_number', 'currency',
                      'currency_symbol', 'invoice_prefix', 'purchase_prefix',
                      'payment_prefix', 'receipt_prefix', 'date_format',
                      'default_weight_unit']:
            value = request.POST.get(field)
            if value is not None:
                setattr(settings_obj, field, value)

        for field in ['sales_tax_rate', 'wht_rate_filer', 'wht_rate_non_filer',
                      'maund_to_kg']:
            value = request.POST.get(field)
            if value:
                setattr(settings_obj, field, value)

        for field in ['financial_year_start', 'session_timeout_minutes']:
            value = request.POST.get(field)
            if value:
                setattr(settings_obj, field, int(value))

        settings_obj.negative_stock_allowed = 'negative_stock_allowed' in request.POST
        settings_obj.low_stock_alert_enabled = 'low_stock_alert_enabled' in request.POST

        # Email & Backup settings
        settings_obj.backup_enabled = 'backup_enabled' in request.POST
        settings_obj.report_enabled = 'report_enabled' in request.POST
        for field in ['backup_email', 'backup_email_secondary']:
            value = request.POST.get(field, '').strip()
            setattr(settings_obj, field, value)
        # Email password — encrypt if new value provided, keep existing if empty
        new_pw = request.POST.get('backup_email_password', '').strip()
        if new_pw:
            settings_obj.set_email_password(new_pw)

        if 'logo' in request.FILES:
            settings_obj.logo = request.FILES['logo']

        settings_obj.save()
        AuditLog.log(user=request.user, action='UPDATE', model_name='CompanySettings',
                     object_id=settings_obj.pk, object_repr='Company Settings', request=request,
                     description='Company settings updated')
        messages.success(request, 'Settings updated successfully.')
        return redirect('settings_app:index')

    return render(request, 'settings_app/index.html', {'settings': settings_obj})


# ─── FINANCIAL YEAR MANAGEMENT ─────────────────
@login_required
def financial_year_list(request):
    from .models import FinancialYear
    years = FinancialYear.objects.all()
    return render(request, 'settings_app/financial_years.html', {'years': years})


@login_required
def financial_year_create(request):
    from .models import FinancialYear
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        # Validate required fields
        errors = []
        if not name:
            errors.append('Name is required — نام ضروری ہے')
        if not start_date:
            errors.append('Start date is required — شروع تاریخ ضروری ہے')
        if not end_date:
            errors.append('End date is required — آخری تاریخ ضروری ہے')

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'settings_app/financial_year_form.html', {'title': 'Add Financial Year'})

        FinancialYear.objects.create(
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_current='is_current' in request.POST,
        )
        messages.success(request, 'Financial year created.')
        return redirect('settings_app:financial_years')
    return render(request, 'settings_app/financial_year_form.html', {'title': 'Add Financial Year'})


# ─── DATA BACKUP ─────────────────
@login_required
def data_backup(request):
    """Backup & Restore — encrypted SQLite database."""
    import os, shutil
    from datetime import datetime
    from django.conf import settings as django_settings
    from django.http import HttpResponse

    db_path = str(django_settings.DATABASES['default']['NAME'])
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    backup_dir = os.path.join(django_settings.BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # List existing backups
    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith('.sqlite3') or f.endswith('.sqlite3.enc'):
            fpath = os.path.join(backup_dir, f)
            backups.append({
                'name': f,
                'size': os.path.getsize(fpath),
                'date': datetime.fromtimestamp(os.path.getmtime(fpath)),
                'encrypted': f.endswith('.enc'),
            })

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── DOWNLOAD BACKUP ──
        if action == 'download':
            password = request.POST.get('backup_password', '').strip()
            today = __import__("datetime").date.today()

            # Read the database
            with open(db_path, 'rb') as f:
                data = f.read()

            if password:
                # Encrypt with user's password
                try:
                    from cryptography.fernet import Fernet
                    import base64, hashlib
                    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
                    encrypted = Fernet(key).encrypt(data)

                    # Also save local encrypted copy
                    local_path = os.path.join(backup_dir, f'backup_{today}.sqlite3.enc')
                    with open(local_path, 'wb') as f:
                        f.write(encrypted)

                    response = HttpResponse(encrypted, content_type='application/octet-stream')
                    response['Content-Disposition'] = f'attachment; filename="cotton_factory_{today}.sqlite3.enc"'

                    AuditLog.log(user=request.user, action='CREATE', model_name='Backup',
                                 description=f'Encrypted backup downloaded ({len(encrypted)//1024} KB)')
                    return response
                except ImportError:
                    messages.error(request, 'cryptography package not installed. pip install cryptography')
                    return redirect('settings_app:backup')
            else:
                # Plain backup (no encryption)
                local_path = os.path.join(backup_dir, f'backup_{today}.sqlite3')
                shutil.copy2(db_path, local_path)

                response = HttpResponse(data, content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="cotton_factory_{today}.sqlite3"'

                AuditLog.log(user=request.user, action='CREATE', model_name='Backup',
                             description=f'Plain backup downloaded ({len(data)//1024} KB)')
                return response

        # ── RESTORE FROM UPLOAD ──
        elif action == 'restore' and 'restore_file' in request.FILES:
            uploaded = request.FILES['restore_file']
            password = request.POST.get('restore_password', '').strip()
            filename = uploaded.name.lower()

            # Read uploaded file
            file_data = uploaded.read()

            if filename.endswith('.enc') or filename.endswith('.encrypted'):
                # Encrypted backup — need password
                if not password:
                    messages.error(request, '🔐 Password required for encrypted backup — خفیہ بیک اپ کے لیے پاسورڈ ضروری ہے')
                    return redirect('settings_app:backup')
                try:
                    from cryptography.fernet import Fernet, InvalidToken
                    import base64, hashlib
                    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
                    try:
                        file_data = Fernet(key).decrypt(file_data)
                    except InvalidToken:
                        messages.error(request, '❌ Wrong password — cannot decrypt backup — غلط پاسورڈ')
                        return redirect('settings_app:backup')
                except ImportError:
                    messages.error(request, 'cryptography package not installed')
                    return redirect('settings_app:backup')

            # Validate it's a SQLite database
            if not file_data[:16].startswith(b'SQLite format 3'):
                messages.error(request, '❌ Invalid file — not a SQLite database — یہ ڈیٹا بیس فائل نہیں ہے')
                return redirect('settings_app:backup')

            # Auto-backup current database before replacing
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            auto_backup = os.path.join(backup_dir, f'pre_restore_{timestamp}.sqlite3')
            if os.path.exists(db_path):
                shutil.copy2(db_path, auto_backup)

            # Replace database
            with open(db_path, 'wb') as f:
                f.write(file_data)

            # Auto-fix schema if restoring from an older backup
            schema_fixes = 0
            try:
                from django.core.management import call_command
                from io import StringIO
                out = StringIO()
                call_command('fix_old_db', '--apply', stdout=out)
                fix_output = out.getvalue()
                if 'Applied' in fix_output or 'fix(es) applied' in fix_output:
                    schema_fixes = fix_output.count('✅ Added')
            except Exception:
                pass  # Schema fix is best-effort

            AuditLog.log(user=request.user, action='UPDATE', model_name='Backup',
                         description=f'Database restored from {uploaded.name} ({len(file_data)//1024} KB)')

            fix_msg = f' {schema_fixes} schema fix(es) applied.' if schema_fixes else ''
            messages.success(request,
                f'✅ Database restored successfully! ({len(file_data)//1024} KB) '
                f'Your old data was auto-saved to {os.path.basename(auto_backup)}.{fix_msg} '
                f'Please restart the server. — '
                f'ڈیٹا بیس کامیابی سے بحال ہو گیا۔ سرور دوبارہ شروع کریں۔'
            )
            return redirect('settings_app:backup')

        # ── SEND RECOVERY PASSWORD VIA EMAIL ──
        elif action == 'send_recovery':
            cs = CompanySettings.get_settings()
            email_pw = cs.get_email_password() if cs else ''
            if not cs or not cs.backup_email or not email_pw:
                messages.error(request, 'Email not configured. Go to Settings → Email Backup.')
                return redirect('settings_app:backup')

            # The encryption key is in settings — send it
            from django.conf import settings as s
            enc_key = getattr(s, 'DATABASE_ENCRYPTION_KEY', '')

            try:
                import smtplib
                from email.mime.text import MIMEText
                msg = MIMEText(
                    f'Cotton Factory — Database Encryption Key\n\n'
                    f'Your system encryption key is:\n{enc_key}\n\n'
                    f'Keep this safe! Without it, encrypted backups cannot be opened.\n'
                    f'یہ آپ کی خفیہ کلید ہے۔ اسے محفوظ رکھیں۔',
                    'plain', 'utf-8'
                )
                msg['Subject'] = f'🔐 Cotton Factory — Encryption Key Recovery'
                msg['From'] = cs.backup_email
                msg['To'] = cs.backup_email

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(cs.backup_email, email_pw)
                server.sendmail(cs.backup_email, [cs.backup_email], msg.as_string())
                server.quit()
                messages.success(request, '✅ Encryption key sent to your email — خفیہ کلید ای میل پر بھیج دی گئی')
            except Exception as e:
                messages.error(request, f'Email failed: {e}')
            return redirect('settings_app:backup')

    csv_types = [
        ('👥 Parties', 'parties'), ('📦 Products', 'products'),
        ('🏦 Banks', 'bank_accounts'), ('🛒 Purchases', 'purchases'),
        ('📋 Sales', 'sales'), ('💸 Payments', 'payments'),
        ('💰 Receipts', 'receipts'), ('📝 Expenses', 'expenses'),
        ('📝 Cheques', 'cheques'),
    ]

    return render(request, 'settings_app/backup.html', {
        'db_size': db_size,
        'backups': backups[:10],
        'csv_types': csv_types,
    })


# ─── DATA IMPORT ─────────────────
@login_required
def data_import(request):
    import csv, io
    from decimal import Decimal, InvalidOperation

    IMPORT_TYPES = [
        ('units', 'Units — اکائیاں', 'abbreviation, name, name_urdu, conversion_to_base, unit_type'),
        ('categories', 'Categories — زمرے', 'code, name, name_urdu'),
        ('parties', 'Parties — پارٹیاں', 'name, name_urdu, type, phone, whatsapp, city, district, cnic, current_balance, credit_limit, credit_days'),
        ('products', 'Products — مصنوعات', 'name, code, category, unit, current_stock, minimum_stock, source'),
        ('bank_accounts', 'Bank Accounts — بینک', 'bank_name, account_number, account_type, branch, owner_type, opening_balance, current_balance'),
        ('purchases', 'Purchases — خریداری', 'date, purchase_number, supplier, product, quantity, unit, rate, amount, grand_total'),
        ('sales', 'Sales — فروخت', 'date, invoice_number, customer, product, quantity, unit, rate, amount, grand_total'),
        ('payments', 'Payments — ادائیگیاں', 'date, party_name, amount, method, narration'),
        ('receipts', 'Receipts — وصولیاں', 'date, party_name, amount, method, narration'),
        ('expenses', 'Expenses — اخراجات', 'date, category, amount, paid_to, method, description'),
        ('cheques', 'Cheques — چیک', 'cheque_number, date, party, amount, direction, bank_name, status'),
    ]

    if request.method == 'POST' and 'csv_file' in request.FILES:
        f = request.FILES['csv_file']
        import_type = request.POST.get('import_type', 'parties')
        try:
            decoded = f.read().decode('utf-8-sig')  # utf-8-sig handles BOM from Excel
        except UnicodeDecodeError:
            f.seek(0)
            decoded = f.read().decode('latin-1')
        reader = csv.DictReader(io.StringIO(decoded))
        count = 0
        errs = []

        def _dec(val, default='0'):
            """Safely parse decimal from CSV."""
            try:
                return Decimal(str(val or default).strip().replace(',', ''))
            except (InvalidOperation, ValueError):
                return Decimal(default)

        # ─── UNITS ───────────────────────────────────
        if import_type == 'units':
            from apps.products.models import UnitOfMeasurement
            for i, row in enumerate(reader, 1):
                abbr = (row.get('abbreviation') or '').strip()
                name = (row.get('name') or '').strip()
                if not abbr or not name:
                    continue
                conv = _dec(row.get('conversion_to_base'), '1')
                unit_type = (row.get('unit_type') or 'weight').strip().lower()
                if unit_type not in ('weight', 'quantity', 'volume', 'length'):
                    unit_type = 'weight'
                obj, created = UnitOfMeasurement.objects.update_or_create(
                    abbreviation=abbr,
                    defaults={
                        'name': name,
                        'name_urdu': (row.get('name_urdu') or '').strip(),
                        'conversion_to_base': conv,
                        'unit_type': unit_type,
                        'is_base_unit': str(row.get('is_base_unit', '')).strip().lower() in ('true', '1', 'yes'),
                    }
                )
                count += 1

        # ─── CATEGORIES ──────────────────────────────
        elif import_type == 'categories':
            from apps.products.models import Category
            for i, row in enumerate(reader, 1):
                code = (row.get('code') or '').strip()
                name = (row.get('name') or '').strip()
                if not name:
                    continue
                if not code:
                    code = name[:15].upper().replace(' ', '_')
                obj, created = Category.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'name_urdu': (row.get('name_urdu') or '').strip(),
                    }
                )
                count += 1

        # ─── PARTIES ─────────────────────────────────
        elif import_type == 'parties':
            from apps.parties.models import Party
            for i, row in enumerate(reader, 1):
                name = (row.get('name') or row.get('Name') or row.get('party_name') or '').strip()
                if not name:
                    continue
                ptype = (row.get('type') or row.get('party_type') or 'other').strip().lower()
                if ptype not in ('supplier', 'customer', 'both', 'broker', 'transporter', 'employee', 'other'):
                    ptype = 'other'

                # Balance: read current_balance (from our export) or opening_balance (legacy)
                balance = _dec(row.get('current_balance') or row.get('opening_balance'))

                # Determine balance type from sign
                if balance < 0:
                    ob_type = 'credit'
                    ob_val = abs(balance)
                elif balance > 0:
                    ob_type = 'debit'
                    ob_val = balance
                else:
                    ob_type = (row.get('opening_balance_type') or 'debit').strip().lower()
                    ob_val = Decimal('0')

                code = (row.get('code') or '').strip()

                defaults = {
                    'name': name,
                    'party_type': ptype,
                    'name_urdu': (row.get('name_urdu') or '').strip(),
                    'phone_primary': (row.get('phone') or row.get('phone_primary') or '').strip(),
                    'whatsapp': (row.get('whatsapp') or '').strip(),
                    'city': (row.get('city') or '').strip(),
                    'district': (row.get('district') or '').strip(),
                    'province': (row.get('province') or '').strip(),
                    'cnic': (row.get('cnic') or '').strip(),
                    'ntn_number': (row.get('ntn_number') or '').strip(),
                    'opening_balance': ob_val,
                    'opening_balance_type': ob_type,
                    'current_balance': balance,  # Set DIRECTLY — no finalize
                    'credit_limit': _dec(row.get('credit_limit')),
                    'credit_days': int(_dec(row.get('credit_days'))),
                }

                # is_filer
                is_filer_val = str(row.get('is_filer', '')).strip().lower()
                if is_filer_val in ('true', '1', 'yes'):
                    defaults['is_filer'] = True
                elif is_filer_val in ('false', '0', 'no'):
                    defaults['is_filer'] = False

                # Use CODE as unique key (handles duplicate names correctly)
                # Fall back to name if no code
                if code:
                    obj, created = Party.objects.update_or_create(
                        code=code,
                        defaults=defaults,
                    )
                else:
                    defaults['code'] = Party.generate_code(ptype)
                    obj, created = Party.objects.update_or_create(
                        name=name,
                        defaults=defaults,
                    )
                    # If existing party has no code, set one
                    if not created and not obj.code:
                        obj.code = Party.generate_code(ptype)
                        obj.save(update_fields=['code'])
                count += 1

        # ─── PRODUCTS ────────────────────────────────
        elif import_type == 'products':
            from apps.products.models import Product, Category, UnitOfMeasurement
            # Ensure at least one category and unit exist
            default_cat = Category.objects.first()
            if not default_cat:
                default_cat = Category.objects.create(name='General', name_urdu='عام', code='GEN')
            default_unit = UnitOfMeasurement.objects.filter(abbreviation='KG').first()
            if not default_unit:
                default_unit = UnitOfMeasurement.objects.first()
            if not default_unit:
                default_unit = UnitOfMeasurement.objects.create(
                    name='Kilogram', name_urdu='کلوگرام', abbreviation='KG',
                    conversion_to_base=Decimal('1'))

            for i, row in enumerate(reader, 1):
                name = (row.get('name') or row.get('Name') or row.get('product_name') or '').strip()
                if not name:
                    continue
                cat = default_cat
                cat_name = (row.get('category') or '').strip()
                if cat_name:
                    cat = Category.objects.filter(name=cat_name).first()
                    if not cat:
                        cat, _ = Category.objects.get_or_create(
                            name=cat_name,
                            defaults={'code': cat_name[:15].upper().replace(' ', '_')})

                unit = default_unit
                unit_abbr = (row.get('unit') or '').strip()
                if unit_abbr:
                    found = UnitOfMeasurement.objects.filter(abbreviation__iexact=unit_abbr).first() or \
                            UnitOfMeasurement.objects.filter(name__iexact=unit_abbr).first()
                    if found:
                        unit = found
                    else:
                        errs.append(f"Row {i}: Unit '{unit_abbr}' not found, using {default_unit.abbreviation} — اکائی نہیں ملی")

                stock = _dec(row.get('current_stock'))
                min_stock = _dec(row.get('minimum_stock'))
                source = (row.get('source') or 'purchased').strip().lower()
                if source not in ('purchased', 'produced', 'both'):
                    source = 'purchased'

                obj, created = Product.objects.update_or_create(
                    name=name,
                    defaults={
                        'code': (row.get('code') or '').strip() or Product.generate_code(cat.code if cat else 'PROD'),
                        'category': cat, 'unit': unit, 'status': 'active',
                        'current_stock': stock, 'minimum_stock': min_stock,
                        'source': source,
                    }
                )
                count += 1

        # ─── BANK ACCOUNTS ───────────────────────────
        elif import_type == 'bank_accounts':
            from apps.finance.models import BankAccount
            for i, row in enumerate(reader, 1):
                bank_name = (row.get('bank_name') or row.get('Bank') or '').strip()
                acc_num = (row.get('account_number') or row.get('Account') or '').strip()
                if not bank_name:
                    continue
                ob = _dec(row.get('opening_balance'))
                cb = _dec(row.get('current_balance'))
                if not cb and ob:
                    cb = ob
                acc_type = (row.get('account_type') or 'current').strip().lower()
                if acc_type not in ('current', 'savings', 'pk_current', 'pk_savings'):
                    acc_type = 'current'
                _, created = BankAccount.objects.update_or_create(
                    bank_name=bank_name, account_number=acc_num or 'N/A',
                    defaults={
                        'account_type': acc_type,
                        'branch': (row.get('branch') or '').strip(),
                        'owner_type': (row.get('owner_type') or 'own').strip().lower(),
                        'opening_balance': ob,
                        'current_balance': cb,  # Set directly
                    }
                )
                count += 1

        # ─── PURCHASES ───────────────────────────────
        elif import_type == 'purchases':
            from apps.purchases.models import Purchase, PurchaseItem
            from apps.products.models import Product as PProduct, UnitOfMeasurement as PUnit
            from apps.parties.models import Party as PParty
            created_purchases = {}
            for i, row in enumerate(reader, 1):
                supplier_name = (row.get('supplier') or row.get('party') or '').strip()
                date_str = (row.get('date') or '').strip()
                if not supplier_name or not date_str:
                    continue
                try:
                    supplier = PParty.objects.get(name=supplier_name)
                except PParty.DoesNotExist:
                    errs.append(f"Row {i}: Supplier '{supplier_name}' not found — سپلائر نہیں ملا")
                    continue
                gt = _dec(row.get('grand_total') or row.get('amount'))
                pnum = (row.get('purchase_number') or '').strip()
                if pnum and pnum in created_purchases:
                    p = created_purchases[pnum]
                elif pnum and Purchase.objects.filter(purchase_number=pnum).exists():
                    continue  # Skip duplicate
                else:
                    st = _dec(row.get('subtotal')) or gt
                    p = Purchase.objects.create(
                        date=date_str, supplier=supplier,
                        subtotal=st, grand_total=gt,
                        status='final', created_by=request.user,
                    )
                    if pnum:
                        p.purchase_number = pnum
                        p.save(update_fields=['purchase_number'])
                    created_purchases[pnum or f'_new_{p.pk}'] = p
                    count += 1
                # Add item if product column exists
                product_name = (row.get('product') or '').strip()
                if product_name:
                    product = PProduct.objects.filter(name=product_name).first()
                    if product:
                        qty = _dec(row.get('quantity'))
                        rate = _dec(row.get('rate'))
                        amt = _dec(row.get('amount')) or (qty * rate).quantize(Decimal('0.01'))
                        unit_abbr = (row.get('unit') or '').strip()
                        unit = PUnit.objects.filter(abbreviation__iexact=unit_abbr).first() if unit_abbr else product.unit
                        PurchaseItem.objects.create(
                            purchase=p, product=product, unit=unit or product.unit,
                            quantity=qty, rate=rate, net_amount=amt, amount=amt,
                        )
            # NOTE: We do NOT call finalize() — balances are already set via party import.
            # Stock is set via product import. This is historical record only.

        # ─── SALES ────────────────────────────────────
        elif import_type == 'sales':
            from apps.sales.models import Sale, SaleItem
            from apps.products.models import Product as SProduct, UnitOfMeasurement as SUnit
            from apps.parties.models import Party as SParty
            created_sales = {}
            for i, row in enumerate(reader, 1):
                customer_name = (row.get('customer') or row.get('party') or '').strip()
                date_str = (row.get('date') or '').strip()
                if not customer_name or not date_str:
                    continue
                try:
                    customer = SParty.objects.get(name=customer_name)
                except SParty.DoesNotExist:
                    errs.append(f"Row {i}: Customer '{customer_name}' not found")
                    continue
                gt = _dec(row.get('grand_total') or row.get('amount'))
                inum = (row.get('invoice_number') or '').strip()
                if inum and inum in created_sales:
                    s = created_sales[inum]
                elif inum and Sale.objects.filter(invoice_number=inum).exists():
                    continue
                else:
                    st = _dec(row.get('subtotal')) or gt
                    s = Sale.objects.create(
                        date=date_str, customer=customer,
                        subtotal=st, grand_total=gt,
                        status='final', created_by=request.user,
                    )
                    if inum:
                        s.invoice_number = inum
                        s.save(update_fields=['invoice_number'])
                        created_sales[inum] = s
                    count += 1
                # Add item if product column exists
                product_name = (row.get('product') or '').strip()
                if product_name:
                    product = SProduct.objects.filter(name=product_name).first()
                    if product:
                        qty = _dec(row.get('quantity'))
                        rate = _dec(row.get('rate'))
                        amt = _dec(row.get('amount')) or (qty * rate).quantize(Decimal('0.01'))
                        unit_abbr = (row.get('unit') or '').strip()
                        unit = SUnit.objects.filter(abbreviation__iexact=unit_abbr).first() if unit_abbr else product.unit
                        SaleItem.objects.create(
                            sale=s, product=product, unit=unit or product.unit,
                            quantity=qty, rate=rate, net_amount=amt, amount=amt,
                        )
            # NOTE: No finalize() — same reason as purchases.

        # ─── PAYMENTS ─────────────────────────────────
        elif import_type == 'payments':
            from apps.finance.models import PaymentVoucher
            from apps.parties.models import Party
            for i, row in enumerate(reader, 1):
                party_name = (row.get('party_name') or row.get('party') or row.get('Party') or '').strip()
                date_str = (row.get('date') or row.get('Date') or '').strip()
                amt = _dec(row.get('amount') or row.get('Amount'))
                if not party_name or not date_str or not amt:
                    continue
                try:
                    party = Party.objects.get(name=party_name)
                except Party.DoesNotExist:
                    errs.append(f"Row {i}: Party '{party_name}' not found — پارٹی نہیں ملی")
                    continue
                method = (row.get('method') or row.get('payment_method') or 'cash').strip().lower()
                if method not in ('cash', 'bank', 'cheque', 'online', 'adjustment'):
                    method = 'cash'
                voucher_num = (row.get('voucher_number') or '').strip()
                if voucher_num and PaymentVoucher.objects.filter(voucher_number=voucher_num).exists():
                    continue  # Skip duplicate
                pv = PaymentVoucher(
                    date=date_str, party=party, amount=amt,
                    payment_method=method,
                    narration=(row.get('narration') or row.get('description') or '').strip(),
                    bank_name=(row.get('bank_name') or '').strip(),
                    status='final',  # Set directly as final
                    created_by=request.user,
                )
                pv.save()
                if voucher_num:
                    pv.voucher_number = voucher_num
                    pv.save(update_fields=['voucher_number'])
                # NOTE: Do NOT call finalize() — balance already set via party import
                count += 1

        # ─── RECEIPTS ─────────────────────────────────
        elif import_type == 'receipts':
            from apps.finance.models import ReceiptVoucher
            from apps.parties.models import Party
            for i, row in enumerate(reader, 1):
                party_name = (row.get('party_name') or row.get('party') or row.get('Party') or '').strip()
                date_str = (row.get('date') or row.get('Date') or '').strip()
                amt = _dec(row.get('amount') or row.get('Amount'))
                if not party_name or not date_str or not amt:
                    continue
                try:
                    party = Party.objects.get(name=party_name)
                except Party.DoesNotExist:
                    errs.append(f"Row {i}: Party '{party_name}' not found — پارٹی نہیں ملی")
                    continue
                method = (row.get('method') or row.get('payment_method') or 'cash').strip().lower()
                if method not in ('cash', 'bank', 'cheque', 'online', 'adjustment'):
                    method = 'cash'
                voucher_num = (row.get('voucher_number') or '').strip()
                if voucher_num and ReceiptVoucher.objects.filter(voucher_number=voucher_num).exists():
                    continue  # Skip duplicate
                rv = ReceiptVoucher(
                    date=date_str, party=party, amount=amt,
                    payment_method=method,
                    narration=(row.get('narration') or row.get('description') or '').strip(),
                    bank_name=(row.get('bank_name') or '').strip(),
                    status='final',
                    created_by=request.user,
                )
                rv.save()
                if voucher_num:
                    rv.voucher_number = voucher_num
                    rv.save(update_fields=['voucher_number'])
                # NOTE: Do NOT call finalize() — balance already set via party import
                count += 1

        # ─── EXPENSES ─────────────────────────────────
        elif import_type == 'expenses':
            from apps.finance.models import Expense
            VALID_CATS = [c[0] for c in Expense.CATEGORY_CHOICES]
            for i, row in enumerate(reader, 1):
                cat = (row.get('category') or 'misc').strip().lower()
                if cat not in VALID_CATS:
                    cat = 'misc'
                amt = _dec(row.get('amount'))
                date_str = (row.get('date') or '').strip()
                if not date_str or not amt:
                    continue
                method = (row.get('method') or row.get('payment_method') or 'cash').strip().lower()
                if method not in ('cash', 'bank', 'cheque', 'online'):
                    method = 'cash'
                Expense.objects.create(
                    date=date_str, category=cat, amount=amt,
                    paid_to=(row.get('paid_to') or '').strip(),
                    payment_method=method,
                    description=(row.get('description') or '').strip(),
                    created_by=request.user,
                )
                count += 1

        # ─── CHEQUES ──────────────────────────────────
        elif import_type == 'cheques':
            from apps.finance.models import Cheque as ChqModel
            from apps.parties.models import Party as CParty
            for i, row in enumerate(reader, 1):
                party_name = (row.get('party') or row.get('party_name') or '').strip()
                cheque_num = (row.get('cheque_number') or '').strip()
                date_str = (row.get('date') or row.get('date_on_cheque') or '').strip()
                if not party_name or not cheque_num or not date_str:
                    continue
                try:
                    party = CParty.objects.get(name=party_name)
                except CParty.DoesNotExist:
                    errs.append(f"Row {i}: Party '{party_name}' not found")
                    continue
                amt = _dec(row.get('amount'))
                direction = (row.get('direction') or 'received').strip().lower()
                if direction not in ('issued', 'received'):
                    direction = 'received'
                status = (row.get('status') or 'pending').strip().lower()
                if status not in ('pending', 'deposited', 'cleared', 'bounced', 'cancelled'):
                    status = 'pending'
                chq = ChqModel.objects.create(
                    cheque_number=cheque_num,
                    bank_name=(row.get('bank_name') or row.get('bank') or '').strip(),
                    amount=amt, date_on_cheque=date_str,
                    direction=direction, party=party,
                    status=status,
                    notes=(row.get('notes') or '').strip(),
                )
                # Cheque just recorded — no receipt/payment created
                # Balances are set via party import, so we don't create vouchers
                count += 1

        if errs:
            for e in errs[:10]:
                messages.warning(request, e)
            if len(errs) > 10:
                messages.warning(request, f'... and {len(errs)-10} more errors')
        messages.success(request, f'Imported {count} {import_type} successfully — {count} کامیابی سے درآمد ہوئے')
        AuditLog.log(user=request.user, action='CREATE', model_name='DataImport',
                     description=f'Imported {count} {import_type}')
        return redirect('settings_app:data_import')

    EXPORT_TYPES = [
        ('units', '📏', 'Units', 'اکائیاں', '#f3f4f6'),
        ('categories', '📁', 'Categories', 'زمرے', '#f3f4f6'),
        ('parties', '👥', 'Parties', 'پارٹیاں', '#f3f4f6'),
        ('products', '📦', 'Products', 'مصنوعات', '#f3f4f6'),
        ('bank_accounts', '🏦', 'Bank Accounts', 'بینک', '#f3f4f6'),
        ('purchases', '🛒', 'Purchases', 'خریداری', '#fff7ed'),
        ('sales', '📋', 'Sales', 'فروخت', '#eff6ff'),
        ('payments', '💸', 'Payments', 'ادائیگیاں', '#fef2f2'),
        ('receipts', '💰', 'Receipts', 'وصولیاں', '#f0fdf4'),
        ('expenses', '📝', 'Expenses', 'اخراجات', '#fffbeb'),
        ('cheques', '📝', 'Cheques', 'چیک', '#fef3c7'),
        ('adjustments', '🔄', 'Adjustments', 'ایڈجسٹمنٹ', '#f5f3ff'),
    ]
    return render(request, 'settings_app/data_import.html', {
        'title': 'Import / Export Data — ڈیٹا درآمد / برآمد',
        'import_types': IMPORT_TYPES,
        'export_types': EXPORT_TYPES,
    })

@login_required
@require_POST
def test_backup_email(request):
    """Manually trigger a backup email for testing."""
    from .backup_email import send_backup_email
    try:
        result = send_backup_email()
        if result:
            messages.success(request, '✓ Backup email sent successfully! Check your inbox. — بیک اپ ای میل بھیج دی گئی!')
        else:
            messages.error(request, 'Backup email failed. Check email settings. — ای میل نہیں بھیجی جا سکی۔ سیٹنگز چیک کریں۔')
    except Exception as e:
        messages.error(request, f'Error: {e}')
    return redirect('settings_app:index')


@login_required
@require_POST
def test_report_email(request):
    """Manually trigger a report email for testing."""
    report_type = request.POST.get('report_type', 'morning')
    try:
        if report_type == 'evening':
            from .backup_email import send_evening_report
            result = send_evening_report()
            label = 'Evening summary'
        else:
            from .backup_email import send_morning_report
            result = send_morning_report()
            label = 'Morning agenda'

        if result:
            messages.success(request, f'✓ {label} email sent! Check your inbox. — {label} ای میل بھیج دی گئی!')
        else:
            messages.error(request, 'Report email failed. Check email settings. — ای میل نہیں بھیجی جا سکی۔')
    except Exception as e:
        messages.error(request, f'Error: {e}')
    return redirect('settings_app:index')



@login_required
def data_export(request):
    """Export any data type as CSV."""
    import csv
    export_type = request.GET.get('type', '')
    if not export_type:
        return render(request, 'settings_app/data_import.html', {
            'title': 'Import / Export Data — ڈیٹا درآمد / برآمد',
            'import_types': [],
        })

    from django.http import HttpResponse
    from apps.parties.models import Party
    from apps.products.models import Product, Category, UnitOfMeasurement
    from apps.finance.models import PaymentVoucher, ReceiptVoucher, Expense, BankAccount, CrossPartyAdjustment
    from apps.purchases.models import Purchase, PurchaseItem
    from apps.sales.models import Sale, SaleItem

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="export_{export_type}_{__import__("datetime").date.today()}.csv"'
    response.write('\ufeff')  # BOM for Excel
    writer = csv.writer(response)

    if export_type == 'units':
        writer.writerow(['abbreviation', 'name', 'name_urdu', 'conversion_to_base',
                         'unit_type', 'is_base_unit', 'sort_order'])
        for u in UnitOfMeasurement.objects.all().order_by('sort_order'):
            writer.writerow([u.abbreviation, u.name, u.name_urdu, u.conversion_to_base,
                             u.unit_type, u.is_base_unit, u.sort_order])

    elif export_type == 'categories':
        writer.writerow(['code', 'name', 'name_urdu', 'is_default'])
        for c in Category.objects.all().order_by('sort_order', 'name'):
            writer.writerow([c.code, c.name, c.name_urdu, c.is_default])

    elif export_type == 'parties':
        writer.writerow(['code', 'name', 'name_urdu', 'type', 'phone', 'whatsapp', 'city', 'district',
                         'province', 'cnic', 'ntn_number', 'is_filer', 'current_balance',
                         'credit_limit', 'credit_days'])
        for p in Party.objects.filter(is_active=True).order_by('name'):
            writer.writerow([p.code, p.name, p.name_urdu, p.party_type, p.phone_primary, p.whatsapp,
                             p.city, p.district, p.province, p.cnic, p.ntn_number, p.is_filer,
                             p.current_balance, p.credit_limit, p.credit_days])

    elif export_type == 'products':
        writer.writerow(['code', 'name', 'category', 'unit', 'current_stock',
                         'minimum_stock', 'source', 'status'])
        for p in Product.objects.filter(status='active').select_related('category', 'unit').order_by('name'):
            writer.writerow([p.code, p.name, p.category.name if p.category else '',
                             p.unit.abbreviation if p.unit else '', p.current_stock,
                             p.minimum_stock, p.source, p.status])

    elif export_type == 'bank_accounts':
        writer.writerow(['bank_name', 'account_number', 'account_type', 'branch', 'owner_type',
                         'party_name', 'opening_balance', 'current_balance'])
        for b in BankAccount.objects.select_related('party').all():
            writer.writerow([b.bank_name, b.account_number, b.account_type, b.branch,
                             b.owner_type, b.party.name if b.party else '',
                             b.opening_balance, b.current_balance])

    elif export_type == 'purchases':
        writer.writerow(['date', 'purchase_number', 'supplier', 'product', 'quantity', 'unit', 'rate',
                         'amount', 'subtotal', 'grand_total', 'status'])
        for p in Purchase.objects.filter(status='final').select_related('supplier').order_by('date'):
            items = p.items.select_related('product', 'unit').all()
            for item in items:
                writer.writerow([p.date, p.purchase_number, p.supplier.name,
                                 item.product.name, item.quantity, item.unit.abbreviation if item.unit else '',
                                 item.rate, item.net_amount, p.subtotal, p.grand_total, p.status])
            if not items.exists():
                writer.writerow([p.date, p.purchase_number, p.supplier.name,
                                 '', '', '', '', '', p.subtotal, p.grand_total, p.status])

    elif export_type == 'sales':
        writer.writerow(['date', 'invoice_number', 'customer', 'product', 'quantity', 'unit', 'rate',
                         'amount', 'subtotal', 'grand_total', 'status'])
        for s in Sale.objects.filter(status='final').select_related('customer').order_by('date'):
            items = s.items.select_related('product', 'unit').all()
            for item in items:
                writer.writerow([s.date, s.invoice_number, s.customer.name,
                                 item.product.name, item.quantity, item.unit.abbreviation if item.unit else '',
                                 item.rate, item.net_amount, s.subtotal, s.grand_total, s.status])
            if not items.exists():
                writer.writerow([s.date, s.invoice_number, s.customer.name,
                                 '', '', '', '', '', s.subtotal, s.grand_total, s.status])

    elif export_type == 'payments':
        writer.writerow(['date', 'voucher_number', 'party_name', 'amount', 'method',
                         'bank_name', 'narration', 'status'])
        for p in PaymentVoucher.objects.filter(status='final').select_related('party', 'bank_account').order_by('date'):
            writer.writerow([p.date, p.voucher_number, p.party.name, p.amount,
                             p.payment_method, p.bank_account.bank_name if p.bank_account else '',
                             p.narration, p.status])

    elif export_type == 'receipts':
        writer.writerow(['date', 'voucher_number', 'party_name', 'amount', 'method',
                         'bank_name', 'narration', 'status'])
        for r in ReceiptVoucher.objects.filter(status='final').select_related('party', 'bank_account').order_by('date'):
            writer.writerow([r.date, r.voucher_number, r.party.name, r.amount,
                             r.payment_method, r.bank_account.bank_name if r.bank_account else '',
                             r.narration, r.status])

    elif export_type == 'expenses':
        writer.writerow(['date', 'category', 'amount', 'paid_to', 'method', 'description'])
        for e in Expense.objects.all().order_by('date'):
            writer.writerow([e.date, e.category, e.amount, e.paid_to, e.payment_method, e.description])

    elif export_type == 'adjustments':
        writer.writerow(['date', 'voucher_number', 'from_party', 'to_party', 'amount', 'narration', 'status'])
        for a in CrossPartyAdjustment.objects.filter(status='final').select_related('from_party', 'to_party').order_by('date'):
            writer.writerow([a.date, a.voucher_number, a.from_party.name, a.to_party.name,
                             a.amount, a.narration, a.status])

    elif export_type == 'cheques':
        from apps.finance.models import Cheque
        writer.writerow(['cheque_number', 'date_on_cheque', 'party', 'amount', 'direction',
                         'bank_name', 'status', 'notes'])
        for ch in Cheque.objects.select_related('party').order_by('date_on_cheque'):
            writer.writerow([ch.cheque_number, ch.date_on_cheque, ch.party.name, ch.amount,
                             ch.direction, ch.bank_name, ch.status, ch.notes])

    elif export_type == 'all':
        # Full database dump — all tables in one ZIP
        import zipfile, io as sysio

        zip_buffer = sysio.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. Units (MUST be first for restore)
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['abbreviation', 'name', 'name_urdu', 'conversion_to_base',
                         'unit_type', 'is_base_unit', 'sort_order'])
            for u in UnitOfMeasurement.objects.all().order_by('sort_order'):
                w.writerow([u.abbreviation, u.name, u.name_urdu, u.conversion_to_base,
                             u.unit_type, u.is_base_unit, u.sort_order])
            zf.writestr('01_units.csv', csv_buf.getvalue())

            # 2. Categories
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['code', 'name', 'name_urdu', 'is_default'])
            for c in Category.objects.all().order_by('sort_order', 'name'):
                w.writerow([c.code, c.name, c.name_urdu, c.is_default])
            zf.writestr('02_categories.csv', csv_buf.getvalue())

            # 3. Parties
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['code', 'name', 'name_urdu', 'type', 'phone', 'whatsapp', 'city', 'district',
                         'province', 'cnic', 'ntn_number', 'is_filer', 'current_balance',
                         'credit_limit', 'credit_days'])
            for p in Party.objects.filter(is_active=True).order_by('name'):
                w.writerow([p.code, p.name, p.name_urdu, p.party_type, p.phone_primary, p.whatsapp,
                             p.city, p.district, p.province, p.cnic, p.ntn_number, p.is_filer,
                             p.current_balance, p.credit_limit, p.credit_days])
            zf.writestr('03_parties.csv', csv_buf.getvalue())

            # 4. Products
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['code', 'name', 'category', 'unit', 'current_stock',
                         'minimum_stock', 'source', 'status'])
            for p in Product.objects.filter(status='active').select_related('category', 'unit'):
                w.writerow([p.code, p.name, p.category.name if p.category else '',
                             p.unit.abbreviation if p.unit else '', p.current_stock,
                             p.minimum_stock, p.source, p.status])
            zf.writestr('04_products.csv', csv_buf.getvalue())

            # 5. Bank Accounts
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['bank_name', 'account_number', 'account_type', 'branch', 'owner_type',
                         'opening_balance', 'current_balance'])
            for b in BankAccount.objects.all():
                w.writerow([b.bank_name, b.account_number, b.account_type, b.branch,
                             b.owner_type, b.opening_balance, b.current_balance])
            zf.writestr('05_bank_accounts.csv', csv_buf.getvalue())

            # 6. Purchases
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['date', 'purchase_number', 'supplier', 'product', 'quantity', 'unit',
                         'rate', 'amount', 'subtotal', 'grand_total'])
            for p in Purchase.objects.filter(status='final').select_related('supplier').order_by('date'):
                for item in p.items.select_related('product', 'unit').all():
                    w.writerow([p.date, p.purchase_number, p.supplier.name, item.product.name,
                                item.quantity, item.unit.abbreviation if item.unit else '',
                                item.rate, item.net_amount, p.subtotal, p.grand_total])
            zf.writestr('06_purchases.csv', csv_buf.getvalue())

            # 7. Sales
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['date', 'invoice_number', 'customer', 'product', 'quantity', 'unit',
                         'rate', 'amount', 'subtotal', 'grand_total'])
            for s in Sale.objects.filter(status='final').select_related('customer').order_by('date'):
                for item in s.items.select_related('product', 'unit').all():
                    w.writerow([s.date, s.invoice_number, s.customer.name, item.product.name,
                                item.quantity, item.unit.abbreviation if item.unit else '',
                                item.rate, item.net_amount, s.subtotal, s.grand_total])
            zf.writestr('07_sales.csv', csv_buf.getvalue())

            # 8. Payments
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['date', 'voucher_number', 'party_name', 'amount', 'method',
                         'bank_name', 'narration'])
            for p in PaymentVoucher.objects.filter(status='final').select_related('party').order_by('date'):
                w.writerow([p.date, p.voucher_number, p.party.name, p.amount,
                             p.payment_method, p.bank_account.bank_name if p.bank_account else '',
                             p.narration])
            zf.writestr('08_payments.csv', csv_buf.getvalue())

            # 9. Receipts
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['date', 'voucher_number', 'party_name', 'amount', 'method',
                         'bank_name', 'narration'])
            for r in ReceiptVoucher.objects.filter(status='final').select_related('party').order_by('date'):
                w.writerow([r.date, r.voucher_number, r.party.name, r.amount,
                             r.payment_method, r.bank_account.bank_name if r.bank_account else '',
                             r.narration])
            zf.writestr('09_receipts.csv', csv_buf.getvalue())

            # 10. Expenses
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['date', 'category', 'amount', 'paid_to', 'method', 'description'])
            for e in Expense.objects.all().order_by('date'):
                w.writerow([e.date, e.category, e.amount, e.paid_to, e.payment_method, e.description])
            zf.writestr('10_expenses.csv', csv_buf.getvalue())

            # 11. Cheques
            from apps.finance.models import Cheque as ChqExp
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['cheque_number', 'date_on_cheque', 'party', 'amount', 'direction',
                         'bank_name', 'status', 'notes'])
            for ch in ChqExp.objects.select_related('party').order_by('date_on_cheque'):
                w.writerow([ch.cheque_number, ch.date_on_cheque, ch.party.name, ch.amount,
                             ch.direction, ch.bank_name, ch.status, ch.notes])
            zf.writestr('11_cheques.csv', csv_buf.getvalue())

            # 12. Adjustments
            csv_buf = sysio.StringIO()
            w = csv.writer(csv_buf)
            w.writerow(['date', 'voucher_number', 'from_party', 'to_party', 'amount', 'narration'])
            for a in CrossPartyAdjustment.objects.filter(status='final').select_related('from_party', 'to_party').order_by('date'):
                w.writerow([a.date, a.voucher_number, a.from_party.name, a.to_party.name,
                             a.amount, a.narration])
            zf.writestr('12_adjustments.csv', csv_buf.getvalue())

            # RESTORE_ORDER.txt — instructions
            zf.writestr('RESTORE_ORDER.txt',
                'COTTON FACTORY — BACKUP RESTORE ORDER\n'
                '======================================\n\n'
                'Import CSV files in this EXACT order:\n\n'
                '  1. 01_units.csv        (Units — اکائیاں)\n'
                '  2. 02_categories.csv   (Categories — زمرے)\n'
                '  3. 03_parties.csv      (Parties — پارٹیاں)\n'
                '  4. 04_products.csv     (Products — مصنوعات)\n'
                '  5. 05_bank_accounts.csv (Bank Accounts — بینک)\n'
                '  6. 06_purchases.csv    (Purchases — خریداری)\n'
                '  7. 07_sales.csv        (Sales — فروخت)\n'
                '  8. 08_payments.csv     (Payments — ادائیگیاں)\n'
                '  9. 09_receipts.csv     (Receipts — وصولیاں)\n'
                ' 10. 10_expenses.csv     (Expenses — اخراجات)\n'
                ' 11. 11_cheques.csv      (Cheques — چیک)\n'
                ' 12. 12_adjustments.csv  (Not imported — for reference)\n\n'
                'IMPORTANT:\n'
                '  - Units MUST be imported FIRST (rates depend on unit conversion)\n'
                '  - Categories before Products\n'
                '  - Parties before Purchases/Sales/Payments/Receipts\n'
                '  - Balances are set directly — do NOT run recalculate_balances\n'
                '  - OR: Just restore the .sqlite3 backup file (Settings → Backup)\n'
            )

        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="full_export_{__import__("datetime").date.today()}.zip"'
        return response

    return response
