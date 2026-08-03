from django.urls import path
from . import views
from .cost_analysis import purchase_cost_analysis
from .pdf_views import sale_invoice_pdf, purchase_invoice_pdf, payment_voucher_pdf, receipt_voucher_pdf, party_statement_pdf

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('purchases/', views.purchase_register, name='purchase_register'),
    path('purchases/by-supplier/', views.purchase_by_supplier, name='purchase_by_supplier'),
    path('purchases/by-product/', views.purchase_by_product, name='purchase_by_product'),
    path('sales/', views.sales_register, name='sales_register'),
    path('sales/by-customer/', views.sales_by_customer, name='sales_by_customer'),
    path('sales/by-product/', views.sales_by_product, name='sales_by_product'),
    path('day-book/', views.day_book, name='day_book'),
    path('cash-book/', views.cash_book, name='cash_book'),
    path('bank-book/', views.bank_book, name='bank_book'),
    path('payables/', views.outstanding_payables, name='payables'),
    path('receivables/', views.outstanding_receivables, name='receivables'),
    path('profit-loss/', views.profit_loss, name='profit_loss'),
    path('trial-balance/', views.trial_balance, name='trial_balance'),
    path('stock/', views.stock_report, name='stock_report'),
    path('party-ledger/', views.party_ledger, name='party_ledger'),
    path('party-ledger/<int:pk>/', views.party_ledger, name='party_ledger_detail'),
    path('broker-commission/', views.broker_commission_report, name='broker_commission'),
    path('ginning/', views.ginning_report, name='ginning_report'),
    path('monthly/', views.monthly_comparison, name='monthly_comparison'),
    path('aging/', views.aging_report, name='aging_report'),
    path('stock-reconciliation/', views.stock_reconciliation, name='stock_reconciliation'),
    path('accounts-overview/', views.accounts_overview, name='accounts_overview'),
    path('overdue/', views.overdue_invoices, name='overdue_invoices'),
    path('expense-analysis/', views.expense_analysis, name='expense_analysis'),
    path('purchase-cost/', purchase_cost_analysis, name='purchase_cost'),
    path('export/<str:report_type>/', views.export_csv, name='export_csv'),
    # PDF Invoices
    path('pdf/sale/<int:pk>/', sale_invoice_pdf, name='sale_pdf'),
    path('pdf/purchase/<int:pk>/', purchase_invoice_pdf, name='purchase_pdf'),
    path('pdf/payment/<int:pk>/', payment_voucher_pdf, name='payment_pdf'),
    path('pdf/receipt/<int:pk>/', receipt_voucher_pdf, name='receipt_pdf'),
    path('pdf/statement/<int:pk>/', party_statement_pdf, name='statement_pdf'),
]
