import uuid
from datetime import date
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType

from .models import (
    CustomUser, Income, Expense, Budget,
    General_Saving, Savings_Goal, Repayment_Goal, History
)

current_year = date.today().year


def update_goal_with_history(goal_instance, field_name, action_type, amount, date):
    if action_type == 'add':
        setattr(goal_instance, field_name, getattr(goal_instance, field_name) + amount)
    elif action_type == 'remove':
        setattr(goal_instance, field_name, getattr(goal_instance, field_name) - amount)
    else:
        raise ValueError("Invalid action type")

    goal_instance.save()

    History.objects.create(
        action=action_type,
        amount=amount,
        date=date,
        content_type=ContentType.objects.get_for_model(goal_instance),
        object_id=goal_instance.id,
    )


def create_dummy_history_entry(user):
    general_ct = ContentType.objects.get_for_model(General_Saving)
    goal_ct = ContentType.objects.get_for_model(Savings_Goal)
    repayment_ct = ContentType.objects.get_for_model(Repayment_Goal)

    general_savings = General_Saving.objects.filter(user=user)
    savings_goals = Savings_Goal.objects.filter(user=user)
    repayment_goals = Repayment_Goal.objects.filter(user=user)

    for i, obj in enumerate(general_savings):
        entries = [('add', 100), ('remove', 30)]
        for j, (action, amt) in enumerate(entries):
            History.objects.create(
                user=user,
                date=date(2025, 3 + j, 20),
                action=action,
                amount=Decimal(amt),
                content_type=general_ct,
                object_id=obj.id
            )

    for i, obj in enumerate(savings_goals):
        entries = [('add', 100), ('remove', 50)]
        for j, (action, amt) in enumerate(entries):
            History.objects.create(
                user=user,
                date=date(2025, 3 + j, 20),
                action=action,
                amount=Decimal(amt),
                content_type=goal_ct,
                object_id=obj.id
            )

    for i, obj in enumerate(repayment_goals):
        entries = [('add', 200), ('remove', 100)]
        for j, (action, amt) in enumerate(entries):
            History.objects.create(
                user=user,
                date=date(2025, 2 + j, 20),
                action=action,
                amount=Decimal(amt),
                content_type=repayment_ct,
                object_id=obj.id
            )


def populate_dummy_data(user):
    Income.objects.bulk_create([
        Income(user=user, category='salary', amount=3200.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Income(user=user, category='extra income', amount=300.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Income(user=user, category='other', amount=30.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Income(user=user, category='investments', amount=80.00, date=date(current_year, 1, 15), recurring_monthly='no'),
        Income(user=user, category='custom', custom_category='Etsy', amount=300.00, date=date(current_year, 5, 15), recurring_monthly='yes'),
    ])

    Expense.objects.bulk_create([
        Expense(user=user, category='housing', amount=1400.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Expense(user=user, category='personal', amount=200.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Expense(user=user, category='food', amount=300.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Expense(user=user, category='entertainment', amount=60.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Expense(user=user, category='debt', amount=150.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Expense(user=user, category='savings', amount=200.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
    ])

    Budget.objects.bulk_create([
        Budget(user=user, category='savings', amount=400.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Budget(user=user, category='debt', amount=200.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
        Budget(user=user, category='food', amount=300.00, date=date(current_year, 1, 15), recurring_monthly='yes'),
    ])

    General_Saving.objects.bulk_create([
        General_Saving(user=user, savings_name='Emergency Fund', amount=1100.00, date=date(current_year, 3, 15)),
        General_Saving(user=user, savings_name='Main Savings', amount=2800.00, date=date(current_year, 1, 15)),
    ])

    Savings_Goal.objects.bulk_create([
        Savings_Goal(user=user, category='travel / holiday', goal_name='Italy Trip', goal_amount=2500.00, current_amount=800.00, deadline_ongoing='no', deadline=date(current_year, 1, 15)),
        Savings_Goal(user=user, category='new home', goal_name='First Home', goal_amount=50000.00, current_amount=20000.00, deadline_ongoing='yes', deadline=None),
    ])

    Repayment_Goal.objects.bulk_create([
        Repayment_Goal(user=user, category='credit card', goal_name='Barclays Credit Card', goal_amount=2500.00, current_amount=2100.00, deadline_ongoing='no', deadline=date(current_year, 10, 15)),
        Repayment_Goal(user=user, category='credit card', goal_name='Natwest Credit Card', goal_amount=700.00, current_amount=300.00, deadline_ongoing='no', deadline=date(current_year, 8, 15)),
    ])

    create_dummy_history_entry(user)


def create_guest_user():
    guest_email = f"guest_{uuid.uuid4().hex[:10]}@example.com"
    guest_user = CustomUser.objects.create_user(
        email=guest_email,
        first_name="Guest",
        last_name="User",
        password=None,
        is_guest=True
    )
    populate_dummy_data(guest_user)
    return guest_user