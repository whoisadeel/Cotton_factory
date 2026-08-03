from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('chart/', views.chart_of_accounts, name='chart'),
    path('account/create/', views.account_create, name='account_create'),
    path('account/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('account/<int:pk>/ledger/', views.account_ledger, name='account_ledger'),
    path('group/create/', views.group_create, name='group_create'),
    path('journals/', views.journal_list, name='journal_list'),
    path('journals/create/', views.journal_create, name='journal_create'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
]
