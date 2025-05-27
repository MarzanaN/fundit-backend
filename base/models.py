from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.crypto import get_random_string
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)
    
    
def generate_user_id():
    return 'ID-' + get_random_string(length=8).upper()


class CustomUser(AbstractUser):
    user_id = models.CharField(max_length=20, unique=True, default=generate_user_id, editable=False)
    first_name = models.CharField(max_length=100, blank=False)
    last_name = models.CharField(max_length=100, blank=False)

    SEX_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    sex = models.CharField(max_length=6, choices=SEX_CHOICES, blank=True, null=True)

    dob = models.DateField(null=True, blank=True)

    is_guest = models.BooleanField(default=False)

    CURRENCY_CHOICES = [
        ('GBP', 'British Pound (£)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
    ]
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, blank=True, null=True)

    email = models.EmailField(unique=True)

    username = None
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    groups = models.ManyToManyField('auth.Group', related_name='customuser_set', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='customuser_permissions_set', blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user_id})"


class Income(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False)
    date = models.DateField(blank=False)
    
    CATEGORY_CHOICES = [
        ('salary', 'Salary'),
        ('extra income', 'Extra Income'),
        ('investments', 'Investments'),
        ('pension', 'Pension'),
        ('other', 'Other'),
        ('custom', 'Custom')
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, blank=False)
    
 
    custom_category = models.CharField(max_length=100, blank=True) 
    
    RECURRING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]
    recurring_monthly = models.CharField(max_length=3, choices=RECURRING_CHOICES, blank=False)

    def clean(self):
        """Custom validation: Ensure custom_category is filled if 'Custom' category is selected."""
        if self.category == 'custom' and not self.custom_category:
            raise ValidationError({'custom_category': 'Custom category is required when "Custom" is selected.'})
    
    def __str__(self):
        return f"Income of {self.amount} for {self.category} on {self.date}"


class Expense(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False)
    date = models.DateField(blank=False)
    
    CATEGORY_CHOICES = [
        ('housing', 'Housing'),
        ('transport', 'Transport'),
        ('food', 'Food'),
        ('healthcare', 'Healthcare'),
        ('personal', 'Personal'),
        ('entertainment', 'Entertainment'),
        ('debt', 'Debt'),
        ('savings', 'Savings'),
        ('miscellaneous', 'Miscellaneous'),
        ('custom', 'Custom')
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, blank=False)
    
    custom_category = models.CharField(max_length=100, blank=True)  
    
    RECURRING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]
    recurring_monthly = models.CharField(max_length=3, choices=RECURRING_CHOICES, blank=False)

    def clean(self):
        """Custom validation: Ensure custom_category is filled if 'Custom' category is selected."""
        if self.category == 'custom' and not self.custom_category:
            raise ValidationError({'custom_category': 'Custom category is required when "Custom" is selected.'})
    
    def __str__(self):
        return f"Expense {self.amount} for {self.category} on {self.date}"


class Budget(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    CATEGORY_CHOICES = [
        ('housing', 'Housing'),
        ('transport', 'Transport'),
        ('food', 'Food'),
        ('healthcare', 'Healthcare'),
        ('personal', 'Personal'),
        ('entertainment', 'Entertainment'),
        ('debt', 'Debt'),
        ('savings', 'Savings'),
        ('miscellaneous', 'Miscellaneous'),
        ('custom', 'Custom')
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    
    custom_category = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    RECURRING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No I want to assign a month'),
    ]
    recurring_monthly = models.CharField(max_length=3, choices=RECURRING_CHOICES)

    date = models.DateField(blank=True, null=True)

    def clean(self):
        if self.category == 'custom' and not self.custom_category:
            raise ValidationError({'custom_category': 'Custom category is required when "Custom" is selected.'})
        
        if self.recurring_monthly == 'no' and not self.date:
            raise ValidationError({'date': 'Date is required if the budget is not recurring monthly.'})

    def __str__(self):
        category_display = self.get_category_display()
        if self.category == 'custom':
            category_display = self.custom_category or 'Custom'
        return f"Budget £{self.amount} for {category_display}"


class General_Saving(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    savings_name = models.CharField(max_length=100, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False)
    date = models.DateField(blank=False)

    def __str__(self):
        return f"Savings {self.amount} for {self.date}"
    

class Savings_Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    CATEGORY_CHOICES = [
        ('emergency fund', 'Emergency Fund'),
        ('travel / holiday', 'Travel / Holiday'),
        ('new home', 'New Home'),
        ('home renovation', 'Home Renovation'),
        ('car / vehicle', 'Car / Vehicle'),
        ('education / courses', 'Education / Courses'),
        ('wedding / event', 'Wedding / Event'),
        ('tech / gadgets', 'Tech / Gadgets'),
        ('christmas / gifts', 'Christmas / Gifts'),
        ('special event', 'Special Event'),
        ('gifts', 'Gifts'),
        ('rainy day fund', 'Rainy Day Fund'),
        ('investment fund', 'Investment Fund'),
        ('luxury purchase', 'Luxury Purchase'),
        ('other', 'Other')
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, blank=False)
    goal_name = models.CharField(max_length=100, blank=False)
    goal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False)

    current_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)

    RECURRING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No I want to set a deadline'),
    ]
    deadline_ongoing = models.CharField(choices=RECURRING_CHOICES, blank=False)

    deadline = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Savings Goal {self.goal_amount} for {self.category}"


class Repayment_Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    CATEGORY_CHOICES = [
        ('credit card', 'Credit Card'),
        ('loan', 'Loan'),
        ('student loan', 'Student Loan'),
        ('mortgage', 'Mortgage'),
        ('car finance', 'Car Finance'),
        ('buy now pay later', 'But Now Pay Later'),
        ('medical bills', 'Medical Bills'),
        ('overdraft', 'Overdraft'),
        ('utility arrears', 'Utility Arrears'),
        ('tax debt', 'Tax Debt'),
        ('family or friend loan', 'Family or Friend Loan'),
        ('business loan', 'Business Loan'),
        ('other', 'Other')
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, blank=False)
    goal_name = models.CharField(max_length=100, blank=False)
    goal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False)

    current_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)

    RECURRING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No I want to set a deadline'),
    ]
    deadline_ongoing = models.CharField(choices=RECURRING_CHOICES, blank=False)

    deadline = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Repayments Goal {self.goal_amount} for {self.category}"


class History(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField()  

    ACTION_CHOICES = [
        ('add', 'Add'),
        ('remove', 'Remove'),
    ]
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    related_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"{self.get_action_display()} £{self.amount} on {self.related_object} at {self.date}"
    
    class Meta:
        ordering = ['-date']