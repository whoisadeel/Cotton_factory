from django.contrib import admin
from .models import AccountGroup, Account, JournalEntry, JournalLine
admin.site.register(AccountGroup)
admin.site.register(Account)
admin.site.register(JournalEntry)
admin.site.register(JournalLine)
