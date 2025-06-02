from django.contrib import admin

from .models import (
    CustomUser,
    Income,
    Expense,
    Budget,
    General_Saving,
    Savings_Goal,
    Repayment_Goal,
    History,
)

admin.site.register((
    CustomUser,
    Income,
    Expense,
    Budget,
    General_Saving,
    Savings_Goal,
    Repayment_Goal,
    History,
))
