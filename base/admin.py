from django.contrib import admin

# Register your models here.

from .models import CustomUser, Income, Expense, Budget, General_Saving, Savings_Goal, Repayment_Goal, History

admin.site.register((CustomUser, Income, Expense, Budget, General_Saving, Savings_Goal, Repayment_Goal, History))
