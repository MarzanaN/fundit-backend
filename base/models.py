from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.crypto import get_random_string
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Custom manager for the User model where email is the unique identifier
    instead of username. Handles creation of regular users and superusers.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and returns a user with the given email and password.
        Raises an error if email is not provided.
        """
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates and returns a superuser with the given email and password.
        Ensures is_staff and is_superuser are set to True.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


def generate_user_id():
    """
    Generates a random user ID in the format 'ID-XXXXXXXX'
    where X is an uppercase letter or digit.
    """
    return 'ID-' + get_random_string(length=8).upper()


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Uses email instead of username for authentication and includes additional fields.
    First name, Last Name, Email address and Password are used for Registration.
    Email and Password used to log in.
    DOB, Currency and Sex can be updated on the settings page once signed in.
    """

    # Unique user ID generated automatically in the format 'ID-XXXXXXXX'
    user_id = models.CharField(max_length=20, unique=True, default=generate_user_id, editable=False)

    # User's first and last name (required) used for registering user
    first_name = models.CharField(max_length=100, blank=False)
    last_name = models.CharField(max_length=100, blank=False)

    # Optional field for user's sex. User can select options only on the settings page.
    SEX_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    sex = models.CharField(max_length=6, choices=SEX_CHOICES, blank=True, null=True)

    # Optional field for date of birth.User can select options only on the settings page.
    dob = models.DateField(null=True, blank=True)

    # Boolean flag to indicate if the user is a temporary guest. 
    # Used for 'Explore as Guest' sessions and to control guest-specific logic and rendering.
    is_guest = models.BooleanField(default=False)

    # Optional preferred currency for the user. 
    # User can select options only on the settings page and will currency can be updated on displayed data.
    CURRENCY_CHOICES = [
        ('GBP', 'British Pound (£)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
    ]
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, blank=True, null=True)

    # Email is the unique identifier used for authentication.
    email = models.EmailField(unique=True)

    # Disable the default username field from AbstractUser
    username = None
    USERNAME_FIELD = 'email'  # Use email to log in
    REQUIRED_FIELDS = ['first_name', 'last_name']  # Fields required when creating a superuser

    # Assign the custom user manager
    objects = CustomUserManager()

    # Override default group and permission relationships for clarity
    groups = models.ManyToManyField('auth.Group', related_name='customuser_set', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='customuser_permissions_set', blank=True)

    def __str__(self):
        # String representation of the user
        return f"{self.first_name} {self.last_name} ({self.user_id})"
    

class Income(models.Model):
    """
    Income model to record each Income entry for user.
    User can assign a date, income amount, select from pre-defined categories or create
    a custom category and name it. Aswell as assign the income entry as recurring 
    monthly by selecting yes or no to minimise entry effort.
    """
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
    """
    Expense model to record each expense entry for user.
    User can assign a date, expense amount, select from pre-defined categories or create
    a custom category and name it. Aswell as assign the expense entry as recurring 
    monthly by selecting yes or no to minimise entry effort.
    """

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
    """
    Budget model for the user for to budegt for expenses.
    Users can assign a budget for the same predifined expense categories and 
    also apply the budget to every month or assign to a specific month.
    This data will be used on the expense page to help track the users expenses
    and manage finances.
    """

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
    """
    General Savings Model to help users track any savings they have that don't 
    require a goal. Users can assign a name for the saving entry, the amount currently
    saved and the date. The user can then add or remove from the amount saved
    as well as track how long they have been saving with the date field on the 
    Goals page.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    savings_name = models.CharField(max_length=100, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=False)
    date = models.DateField(blank=False)

    def __str__(self):
        return f"Savings {self.amount} for {self.date}"


class Savings_Goal(models.Model):
    """
    Savings Goal Model where the user can create a savings goal and track their
    progress towards that goal. User can select from pre-defined categories and
    name the goal. Assign an aspriring goal amount and deadline for the goal. 
    On the goals page they can update the current amount saved towards the 
    goal and edit the goal entry and track how long they have until the deadline.
    """

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
    """
    Repayment Goal Model where the user can create a repayment goal and track their
    progress towards that goal. User can select from pre-defined categories and
    name the goal. Assign a repayment amount and deadline for the goal. 
    On the goals page they can update the current amount that is paid off towards the 
    goal and edit the goal entry and track how long they have until the deadline.
    """

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
    """
    History Model for the user. This is not a model they can add an entry to themselves. 
    An auto entry gets made everytime they add or remove an amount from the general_savings,
    savings_goal or repayment_goal model. This is tracked through the object_id and 
    content_type. This is so we can display a history log for the different content types entries
    and the user can see the history of each entry.
    """

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