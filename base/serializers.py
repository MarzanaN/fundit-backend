from rest_framework import serializers
from .models import (
    CustomUser, Income, Expense, Budget,
    General_Saving, Savings_Goal, Repayment_Goal, History
)
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import datetime

User = get_user_model()


class CustomUserSerializer(serializers.ModelSerializer):
    is_guest = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'sex', 'dob', 'currency', 'is_guest'
        ]


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_guest=False 
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'sex', 'dob', 'currency']
        extra_kwargs = {
            'email': {'required': True},
            'dob': {'required': False, 'allow_null': True},
            'sex': {'required': False, 'allow_blank': True},
            'currency': {'required': False, 'allow_blank': True},
        }

    def validate_dob(self, value):
        if not value:
            return None

        if not isinstance(value, str):
            return value

        try:
            parsed_date = datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            raise serializers.ValidationError("Date of birth must be in DD-MM-YYYY format.")

        return parsed_date

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class IncomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Income
        fields = '__all__'
        read_only_fields = ['user']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ['user']


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = '__all__'
        read_only_fields = ['user']


class GeneralSavingSerializer(serializers.ModelSerializer):
    class Meta:
        model = General_Saving
        fields = '__all__'
        read_only_fields = ['user']


class SavingsGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Savings_Goal
        fields = '__all__'
        read_only_fields = ['user']


class RepaymentGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repayment_Goal
        fields = '__all__'
        read_only_fields = ['user']


class HistorySerializer(serializers.ModelSerializer):
    related_object_repr = serializers.SerializerMethodField()

    class Meta:
        model = History
        fields = [
            'id', 'user', 'action', 'amount', 'date',  
            'content_type', 'object_id', 'related_object_repr'
        ]
        read_only_fields = ['user', 'date']  

    def get_related_object_repr(self, obj):
        return str(obj.related_object) if obj.related_object else None


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)


class DeleteAccountSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reason = serializers.CharField()
    other_reason = serializers.CharField(required=False, allow_blank=True)
    comments = serializers.CharField(required=False, allow_blank=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)