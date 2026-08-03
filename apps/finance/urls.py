from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/create/', views.payment_create, name='payment_create'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:pk>/edit/', views.payment_edit, name='payment_edit'),
    path('payments/<int:pk>/finalize/', views.payment_finalize, name='payment_finalize'),
    path('payments/<int:pk>/void/', views.payment_void, name='payment_void'),
    path('receipts/', views.receipt_list, name='receipt_list'),
    path('receipts/create/', views.receipt_create, name='receipt_create'),
    path('receipts/<int:pk>/', views.receipt_detail, name='receipt_detail'),
    path('receipts/<int:pk>/edit/', views.receipt_edit, name='receipt_edit'),
    path('receipts/<int:pk>/finalize/', views.receipt_finalize, name='receipt_finalize'),
    path('receipts/<int:pk>/void/', views.receipt_void, name='receipt_void'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('bank-accounts/', views.bank_account_list, name='bank_account_list'),
    path('bank-accounts/create/', views.bank_account_create, name='bank_account_create'),
    path('bank-accounts/<int:pk>/ledger/', views.bank_ledger, name='bank_ledger'),
    path('api/bank-account-quick-add/', views.bank_account_quick_add_api, name='bank_account_quick_add_api'),
    path('cheques/', views.cheque_list, name='cheque_list'),
    path('cheques/create/', views.cheque_create, name='cheque_create'),
    path('cheques/<int:pk>/status/', views.cheque_update_status, name='cheque_update_status'),
    # Bank Reconciliation
    path('reconciliation/', views.reconciliation_list, name='reconciliation_list'),
    path('reconciliation/create/', views.reconciliation_create, name='reconciliation_create'),
    path('transactions/', views.transaction_history, name='transaction_history'),
    # Cross-Party Adjustments
    path('adjustments/', views.adjustment_list, name='adjustment_list'),
    path('adjustments/create/', views.adjustment_create, name='adjustment_create'),
    path('adjustments/<int:pk>/', views.adjustment_detail, name='adjustment_detail'),
    path('adjustments/<int:pk>/edit/', views.adjustment_edit, name='adjustment_edit'),
    path('adjustments/<int:pk>/void/', views.adjustment_void, name='adjustment_void'),
]
