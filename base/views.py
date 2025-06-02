import logging
import os
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.core.management import call_command
from django.db.models import Q
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Budget, Expense, General_Saving, History, Income,
    Repayment_Goal, Savings_Goal
)

from .serializers import (
    BudgetSerializer, CustomUserSerializer, ExpenseSerializer,
    GeneralSavingSerializer, HistorySerializer, IncomeSerializer,
    LoginSerializer, RegisterSerializer, RepaymentGoalSerializer,
    SavingsGoalSerializer, SettingsSerializer
)

from .services import update_goal_with_history, create_guest_user


logger = logging.getLogger(__name__)
User = get_user_model()


# Import View for class-based views, os for path handling, and required Django modules
class FrontendAppView(View):
    # Handles GET requests to serve the React frontend
    def get(self, request):
        # Constructs the full path to the built index.html file in the React build directory
        index_path = os.path.join(settings.REACT_BUILD_DIR, 'index.html')
        
        # Debug: print the absolute path being searched for index.html
        print("Looking for index.html at:", os.path.abspath(index_path))
        
        try:
            # Attempts to open and read the index.html file
            with open(index_path, encoding='utf-8') as f:
                # Returns the contents of index.html with an HTML content type
                return HttpResponse(f.read(), content_type='text/html')
        except FileNotFoundError:
            # If index.html is not found, print debug message
            print("File not found at path:", os.path.abspath(index_path))
            
            # Return a helpful HTML response indicating the build step may have been missed
            return HttpResponse(
                "<h1>index.html not found</h1><p>Did you forget to run <code>npm run build</code> in the frontend?</p>",
                status=501,
                content_type='text/html'
            )


# Exempt this class-based view from CSRF validation
@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    # Use the RegisterSerializer to handle incoming registration data
    serializer_class = RegisterSerializer
    
    # Allow any user (authenticated or not) to access this view
    permission_classes = [permissions.AllowAny]

    # Called after serializer.save(), allows custom behavior after user creation
    def perform_create(self, serializer):
        # Save the user instance from serializer and deactivate the account initially
        user = serializer.save()
        user.is_active = False  # Account is inactive until email is confirmed
        user.save()

        # Generate a unique token and UID for email activation link
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Create activation link pointing to frontend route with UID and token
        activation_link = f"http://localhost:3000/activate/{uid}/{token}/"

        # Email subject and message content
        subject = 'Activate Your Fundit Account'
        message = (
            f'Hello {user.first_name or "there"},\n\n'
            f'Please click the link below to verify your email and activate your account:\n\n'
            f'{activation_link}\n\n'
            'If you did not sign up for Fundit, ignore this email.'
        )

        # Attempt to send the activation email
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,  # Sender email from settings
                [user.email],                 # Recipient
                fail_silently=False           # Raise exception if sending fails
            )
            print("✅ Email sent to:", user.email)  # Debug success message
        except Exception as e:
            print(f"❌ Email sending failed: {e}")  # Debug error message


# View to handle account activation via a POST request
class ActivateAccountView(APIView):
    # No permissions required to access this view
    permission_classes = []  

    # POST method to activate user account using UID and token
    def post(self, request, uidb64, token):
        try:
            # Decode the base64 UID to get the user's primary key
            uid = force_str(urlsafe_base64_decode(uidb64))
            # Retrieve the user instance using the decoded UID
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            # Return error response if decoding fails or user doesn't exist
            return Response({'detail': 'Invalid activation link.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the account is already active
        if user.is_active:
            return Response({'detail': 'Account already activated.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the token
        if default_token_generator.check_token(user, token):
            # Activate the user account and save
            user.is_active = True
            user.save()
            # Return success response
            return Response({'detail': 'Account activated successfully.'}, status=status.HTTP_200_OK)
        else:
            # Return error if the token is invalid or expired
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)


# View to verify user's email using a GET request with UID and token
class VerifyEmailView(APIView):
    # Allow any user (authenticated or not) to access this endpoint
    permission_classes = [permissions.AllowAny]

    # GET method to verify and activate user account
    def get(self, request, uidb64, token):
        try:
            # Decode the base64 UID to get the user's primary key
            uid = urlsafe_base64_decode(uidb64).decode()
            # Retrieve the user object based on the UID
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            # Return an error response if decoding fails or user is not found
            return Response({'error': 'Invalid activation link.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the token is valid for the retrieved user
        if default_token_generator.check_token(user, token):
            # Activate the user's account
            user.is_active = True
            user.save()
            # Return a success response
            return Response({'message': 'Account successfully activated.'}, status=status.HTTP_200_OK)
        else:
            # Return an error response if the token is invalid or expired
            return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)


# API view to handle user login
class LoginView(APIView):
    # Handles POST requests to log in a user
    def post(self, request):
        try:
            # Deserialize and validate incoming data
            serializer = LoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Extract validated email and password
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']

            try:
                # Try to find a user with the given email
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Return 404 if no user with that email exists
                return Response({'detail': 'Email not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Check if the provided password matches the user's password
            if not user.check_password(password):
                # Return 401 Unauthorized if the password is incorrect
                return Response({'detail': 'Incorrect password.'}, status=status.HTTP_401_UNAUTHORIZED)

            # Check if the user's account is activated
            if not user.is_active:
                # Return 403 Forbidden if the account is not activated
                return Response({'detail': 'Account is not activated. Please check your email.'},
                                status=status.HTTP_403_FORBIDDEN)

            # Generate JWT refresh and access tokens for the authenticated user
            refresh = RefreshToken.for_user(user)

            # Return the tokens and serialized user data in the response
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': CustomUserSerializer(user).data
            })

        except Exception as e:
            # Catch any unexpected errors and return a 500 Internal Server Error
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Disables CSRF protection for this view and allows it to be used without authentication
@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequestView(APIView):
    # Allow any user (authenticated or not) to access this view
    permission_classes = [permissions.AllowAny]

    # Handles POST requests to initiate password reset
    def post(self, request):
        # Get the email from the request body
        email = request.data.get('email')
        if not email:
            # Return an error if email is missing
            return Response({'detail': 'Email is required.'}, status=400)

        try:
            # Try to find a user with the provided email
            user = User.objects.get(email=email)

            # Check if the account is active before sending reset link
            if not user.is_active:
                return Response({'detail': 'Account is not activated. Please check your email.'}, status=403)

            # Encode user ID and generate token for password reset
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            # Build the reset link to be sent in the email
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

            # Prepare the email content
            subject = 'Reset Your Fundit Password'
            message = (
                f'Hello {user.first_name or "there"},\n\n'
                f'You requested a password reset. Click the link below to reset your password:\n\n'
                f'{reset_link}\n\n'
                'If you didn’t request this, you can safely ignore it.'
            )

            # Send the password reset email
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False
            )
            print("✅ Password reset email sent to:", user.email)

            # Respond with success message
            return Response({'detail': 'Password reset email sent.'})

        except User.DoesNotExist:
            # Return error if user with given email does not exist
            return Response({'detail': 'No user with that email.'}, status=404)

    
# API view to handle password reset confirmation
class PasswordResetConfirmView(APIView):
    # Allow any user (authenticated or not) to access this view
    permission_classes = [permissions.AllowAny]

    # Handle POST request to reset password
    def post(self, request):
        # Get UID, token, and new password from the request
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        # If any of the required parameters are missing, return an error
        if not uidb64 or not token or not new_password:
            return Response({'detail': 'Missing parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Decode the UID and retrieve the user
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            # Return an error if the user does not exist or UID is invalid
            return Response({'detail': 'Invalid user.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the token is valid for the user
        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        # Set the new password and save the user
        user.set_password(new_password)
        user.save()

        # Return success message
        return Response({'detail': 'Password has been reset successfully.'})

    
# API view to retrieve a user's email based on UID and token
class GetUserEmailView(APIView):
    # Handle POST request
    def post(self, request):
        # Extract UID and token from the request data
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')

        try:
            # Decode UID and retrieve the corresponding user
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            # If decoding fails or user doesn't exist, return error response
            return Response({'detail': 'Invalid link'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the provided token is valid for the user
        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        # Return the user's email if token is valid
        return Response({'email': user.email}, status=status.HTTP_200_OK)


# API view to verify if a password reset token is valid
class VerifyResetTokenView(APIView):
    # Allow access without authentication
    permission_classes = [permissions.AllowAny]

    # Handle GET requests with uidb64 and token in URL
    def get(self, request, uidb64, token):
        try:
            # Decode the user ID from the base64 string
            uid = urlsafe_base64_decode(uidb64).decode()
            # Retrieve the user by primary key
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            # Return error if decoding fails or user does not exist
            return Response({'detail': 'Invalid link.'}, status=400)

        # Check if the token is valid for the user
        if default_token_generator.check_token(user, token):
            # If valid, return the user's email
            return Response({'email': user.email}, status=200)
        else:
            # If token is invalid or expired, return an error response
            return Response({'detail': 'Token is invalid or expired.'}, status=400)


# API view to retrieve the authenticated user's data
class UserView(APIView):
    # Require the user to be authenticated to access this view
    permission_classes = [permissions.IsAuthenticated]

    # Handle GET request to return user data
    def get(self, request):
        user = request.user  # Get the currently authenticated user
        serializer = CustomUserSerializer(user)  # Serialize user data
        return Response(serializer.data)  # Return serialized data in response


# API view to allow authenticated users to update their settings
class UpdateSettingsView(generics.UpdateAPIView):
    serializer_class = SettingsSerializer  # Serializer to validate and update user settings
    permission_classes = [permissions.IsAuthenticated]  # Require authentication

    # Return the user object that will be updated
    def get_object(self):
        return self.request.user  # Return currently authenticated user as the object to update


# API view to handle support request submissions via POST
@api_view(['POST'])
def support_request(request):
    # Extract required fields from request data
    name = request.data.get('name')
    email = request.data.get('email')
    issue_type = request.data.get('issue_type')
    message = request.data.get('message')

    # Validate that all fields are provided
    if not all([name, email, issue_type, message]):
        return Response({"error": "All fields are required."}, status=400)

    # Compose email subject line using issue type and sender name
    subject = f"Support Request: {issue_type.capitalize()} from {name}"
    # Compose the full email message including sender details and message content
    full_message = f"From: {name} <{email}>\n\nIssue: {issue_type}\n\nMessage:\n{message}"

    try:
        # Send email to default support address from configured settings
        send_mail(subject, full_message, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL])
        # Respond with success message on successful email send
        return Response({"message": "Support request sent successfully."}, status=200)
    except Exception as e:
        # Log email sending errors and respond with failure message
        print("Email error:", e)
        return Response({"error": "Failed to send email."}, status=500)


# View to handle creating new Income entries
class IncomeCreateView(generics.CreateAPIView):
    serializer_class = IncomeSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Override to associate the created income entry with the logged-in user
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ViewSet to handle listing, updating, and deleting Income entries
class UpdateIncomeEntriesViewSet(viewsets.ModelViewSet):
    serializer_class = IncomeSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Enable filtering and ordering of queryset results
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['date', 'category']  # Filterable by date and category
    ordering_fields = ['date', 'amount']     # Orderable by date and amount

    # Return queryset filtered by user and optionally by year or month query parameters
    def get_queryset(self):
        user = self.request.user
        queryset = Income.objects.filter(user=user)  # Filter incomes by current user

        # Filter by year if provided in query params
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(date__year=year)

        # Filter by month if provided in query params (format 'YYYY-MM')
        month = self.request.query_params.get('month')
        if month:
            try:
                # Parse year and month from the string
                year_m, month_num = month.split('-')
                start_date = parse_date(f"{year_m}-{month_num}-01")
                # Calculate the end date for filtering the month
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year_m)+1}-01-01")
                else:
                    end_date = parse_date(f"{year_m}-{int(month_num)+1}-01")

                # Filter queryset by dates or recurring monthly incomes
                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date) |
                        Q(recurring_monthly='yes', date__lte=end_date)
                    )
            except (ValueError, TypeError):
                # If parsing fails, ignore the filter and return unfiltered queryset
                pass

        return queryset.order_by('date')  # Return queryset ordered by date


# View to handle creating new Expense entries
class ExpenseCreateView(generics.CreateAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Override to associate the created expense entry with the logged-in user
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ViewSet to handle listing, updating, and deleting Expense entries
class UpdateExpenseEntriesViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]  # Enable filtering on queryset
    filterset_fields = ['category', 'date']  # Filterable by category and date

    # Return queryset filtered by user and optionally by year or month query parameters
    def get_queryset(self):
        user = self.request.user
        queryset = Expense.objects.filter(user=user)  # Filter expenses by current user

        # Filter by year if provided in query params
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(date__year=year)

        # Filter by month if provided in query params (format 'YYYY-MM')
        month = self.request.query_params.get('month')
        if month:
            try:
                # Parse year and month from the string
                year_m, month_num = month.split('-')
                start_date = parse_date(f"{year_m}-{month_num}-01")
                # Calculate the end date for filtering the month
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year_m)+1}-01-01")
                else:
                    end_date = parse_date(f"{year_m}-{int(month_num)+1}-01")

                # Filter queryset by dates or recurring monthly expenses
                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date) |
                        Q(recurring_monthly='yes', date__lte=end_date)
                    )
            except (ValueError, TypeError):
                # If parsing fails, ignore the filter and return unfiltered queryset
                pass

        return queryset.order_by('date')  # Return queryset ordered by date


# View to handle creating new Budget entries
class BudgetCreateView(generics.CreateAPIView):
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Override to associate the created budget entry with the logged-in user
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ViewSet to manage listing, updating, and deleting Budget entries
class UpdateBudgetEntriesViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]  # Enable filtering on queryset
    filterset_fields = ['category', 'date']  # Allow filtering by category and date

    # Return queryset filtered by current user and optionally by month query param
    def get_queryset(self):
        user = self.request.user
        queryset = Budget.objects.filter(user=user)  # Filter budgets by user

        # Filter by month if provided in query params (format 'YYYY-MM')
        month = self.request.query_params.get('month')
        if month:
            try:
                # Parse year and month values
                year, month_num = month.split('-')
                start_date = parse_date(f"{year}-{month_num}-01")
                # Determine end date for the monthly range
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year) + 1}-01-01")
                else:
                    end_date = parse_date(f"{year}-{int(month_num) + 1}-01")

                # Filter budgets within the month or recurring monthly budgets
                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date) |
                        Q(recurring_monthly='yes', date__lte=end_date)
                    )
            except (ValueError, TypeError):
                # Ignore invalid date formats and return unfiltered queryset
                pass

        # Order the results by date and category
        return queryset.order_by('date', 'category')


# View to handle creation of general savings entries
class GeneralSavingsCreateView(generics.CreateAPIView):
    serializer_class = GeneralSavingSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Associate the new general saving entry with the current user
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ViewSet to handle CRUD operations and custom updates for General Savings entries
class UpdateGeneralSavingsEntriesViewSet(viewsets.ModelViewSet):
    queryset = General_Saving.objects.all()  # Base queryset for all General Savings
    serializer_class = GeneralSavingSerializer
    permission_classes = [IsAuthenticated]
    goal_field = 'amount'  # Field name to be updated via custom action

    # Filter queryset by logged-in user and optionally by year and month query params
    def get_queryset(self):
        user = self.request.user
        queryset = General_Saving.objects.filter(user=user)  # Filter by user

        # Filter by year if provided
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(date__year=year)

        # Filter by month if provided (format 'YYYY-MM')
        month = self.request.query_params.get('month')
        if month:
            try:
                year_m, month_num = month.split('-')
                start_date = parse_date(f"{year_m}-{month_num}-01")
                # Determine next month start date for end date filter
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year_m)+1}-01-01")
                else:
                    end_date = parse_date(f"{year_m}-{int(month_num)+1}-01")

                # Filter entries within the month range
                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date)
                    )
            except (ValueError, TypeError):
                # Ignore invalid month format
                pass

        # Order results by date ascending
        return queryset.order_by('date')

    # Override create method to associate new entries with current user
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # Custom action to update the 'amount' field of a specific General Saving entry
    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        try:
            goal = self.get_object()  # Get the General Saving instance by pk
            action_type = request.data.get('action')  # Action type, e.g., 'add' or 'subtract'
            amount_str = request.data.get('amount')  # Amount value as string
            date_str = request.data.get('date')  # Date string, expected 'YYYY-MM-DD' or 'YYYY-MM'

            # Validate and convert amount string to Decimal
            try:
                amount = Decimal(amount_str)
            except (TypeError, ValueError, InvalidOperation):
                return Response({'error': 'Invalid amount'}, status=400)

            # Append day midpoint if only year-month provided
            if date_str and len(date_str) == 7:
                date_str += '-15'
            date = parse_date(date_str)
            if date is None:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

            # Call external helper function to update the goal with history tracking
            update_goal_with_history(goal, self.goal_field, action_type, amount, date)

            return Response({'status': f'{self.goal_field} updated'}, status=status.HTTP_200_OK)

        except Exception as e:
            # Catch-all for unexpected errors during update
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# API view to create a new Savings Goal, associating it with the authenticated user
class SavingsGoalCreateView(generics.CreateAPIView):
    serializer_class = SavingsGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Save the SavingsGoal instance with the current user as owner
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# API view to create a new Repayments Goal, associating it with the authenticated user
class RepaymentsGoalCreateView(generics.CreateAPIView):
    serializer_class = RepaymentGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Save the RepaymentGoal instance with the current user as owner
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# Base ViewSet for managing goals, includes common update logic for amount
class BaseGoalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    goal_field = 'current_amount'  # Field to update via custom action

    # Return queryset filtered by the authenticated user
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    # Ensure new goal instances are saved with the authenticated user as owner
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # Custom action to update the goal amount with history tracking
    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        try:
            goal = self.get_object()  # Get the specific goal object by primary key
            action_type = request.data.get('action')  # e.g., 'add', 'subtract'
            amount_str = request.data.get('amount')  # Amount as string
            date_str = request.data.get('date')  # Date string 'YYYY-MM-DD' or 'YYYY-MM'

            # Validate and convert amount to Decimal
            try:
                amount = Decimal(amount_str)
            except (TypeError, ValueError, InvalidOperation):
                return Response({'error': 'Invalid amount'}, status=400)

            # Append day if only year-month format is provided
            if date_str and len(date_str) == 7:
                date_str += '-15'
            date = parse_date(date_str)
            if date is None:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

            # Call helper function to update goal amount and record history
            update_goal_with_history(goal, self.goal_field, action_type, amount, date)

            return Response({'status': f'{self.goal_field} updated'}, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle unexpected exceptions
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ViewSet for updating Savings Goals, inherits common goal logic from BaseGoalViewSet
class UpdateSavingsGoalsViewSet(BaseGoalViewSet):
    queryset = Savings_Goal.objects.all()  # Use all Savings_Goal instances
    serializer_class = SavingsGoalSerializer
    goal_field = 'current_amount'  # Field to update via the BaseGoalViewSet logic


# ViewSet for updating Repayment Goals, inherits common goal logic from BaseGoalViewSet
class UpdateRepaymentGoalsViewSet(BaseGoalViewSet):
    queryset = Repayment_Goal.objects.all()  # Use all Repayment_Goal instances
    serializer_class = RepaymentGoalSerializer
    goal_field = 'current_amount'  # Field to update via the BaseGoalViewSet logic


# API view to list history entries for a General Saving by its ID (pk)
class GeneralSavingHistoryListView(generics.ListAPIView):
    serializer_class = HistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        general_saving_id = self.kwargs.get('pk')  # Get the ID of the general saving from URL kwargs

        # Get ContentType for the General_Saving model
        content_type = ContentType.objects.get(app_label='base', model='general_saving')
        
        # Return History entries filtered by content_type and object_id, ordered by most recent first
        return History.objects.filter(
            content_type=content_type,
            object_id=general_saving_id
        ).order_by('-date')


# API view to list history entries for a Savings Goal by its ID (pk)
class SavingsGoalHistoryListView(generics.ListAPIView):
    serializer_class = HistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        general_saving_id = self.kwargs.get('pk')  # Get the Savings Goal ID from URL kwargs

        # Get ContentType for the Savings_Goal model
        content_type = ContentType.objects.get(app_label='base', model='savings_goal')
        
        # Return filtered History entries ordered by date descending
        return History.objects.filter(
            content_type=content_type,
            object_id=general_saving_id
        ).order_by('-date')


# API view to list history entries for a Repayment Goal by its ID (pk)
class RepaymentGoalHistoryListView(generics.ListAPIView):
    serializer_class = HistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        general_saving_id = self.kwargs.get('pk')  # Get the Repayment Goal ID from URL kwargs

        # Get ContentType for the Repayment_Goal model
        content_type = ContentType.objects.get(app_label='base', model='repayment_goal')
        
        # Return filtered History entries ordered by date descending
        return History.objects.filter(
            content_type=content_type,
            object_id=general_saving_id
        ).order_by('-date')
    

# API view to create and return tokens for a guest user login
class GuestLoginView(APIView):
    def post(self, request):
        guest_user = create_guest_user()  # Create a new guest user

        # Generate JWT refresh token for the guest user
        refresh = RefreshToken.for_user(guest_user)

        # Return tokens and serialized guest user data in response
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': CustomUserSerializer(guest_user).data
        }, status=status.HTTP_201_CREATED)


# API view to log out the current user
@api_view(['POST'])
def logout_view(request):
    user = request.user
    logout(request)  # Log out the user from the session
    # If the user is a guest user, delete the guest user record
    if getattr(user, 'is_guest', False):
        user.delete()
    return Response({'message': 'Logged out'}, status=status.HTTP_200_OK)


# API view restricted to admin users to trigger cleanup of old guest users
@api_view(['POST'])
@permission_classes([IsAdminUser])  
def cleanup_old_guests(request):
    try:
        # Call custom management command to delete old guest users
        call_command('delete_old_guests')
        return Response({'message': 'Old guest users cleanup completed.'})
    except Exception as e:
        # Return error response if cleanup fails
        return Response({'error': str(e)}, status=500)
    

# API view to allow authenticated users to change their password
class ChangePasswordView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        # Validate that both current and new passwords are provided
        if not current_password or not new_password:
            return Response({'detail': 'Please provide current and new password.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the current password matches the user's password
        if not user.check_password(current_password):
            return Response({'detail': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce minimum length requirement on the new password
        if len(new_password) < 6:
            return Response({'detail': 'New password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        # Set and save the new password
        user.set_password(new_password)
        user.save()

        return Response({'detail': 'Password updated successfully!'}, status=status.HTTP_200_OK)


# API view for authenticated users to request account deletion with feedback
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account_request(request):
    user = request.user
    delete_reason = request.data.get('delete_reason')
    other_reason = request.data.get('other_reason', '')
    comments = request.data.get('comments', '')
    rating = request.data.get('rating')
    confirm = request.data.get('confirm')

    # Confirm user explicitly approved account deletion
    if confirm is not True:
        return Response({"error": "Please confirm account deletion."}, status=400)

    # Validate required fields
    if not delete_reason:
        return Response({"error": "Please provide a reason for deletion."}, status=400)

    if rating is None:
        return Response({"error": "Please provide a satisfaction rating."}, status=400)

    # Validate rating value is an integer between 1 and 5
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return Response({"error": "Rating must be between 1 and 5."}, status=400)
    except (ValueError, TypeError):
        return Response({"error": "Invalid rating format."}, status=400)

    # Handle "Other" reason by requiring user to specify a reason
    final_reason = delete_reason
    if delete_reason == "Other":
        if not other_reason.strip():
            return Response({"error": "Please specify your reason."}, status=400)
        final_reason = f"Other: {other_reason}"

    # Prepare email content to notify admin about account deletion
    subject = f"Account Deletion: {user.email}"
    message = f"""
Account Deletion Request

User: {user.get_full_name()} ({user.email})
Reason: {final_reason}
Comments: {comments}
Satisfaction Rating: {rating}/5
Confirmed: Yes

The account was successfully deleted from the system.
    """

    try:
        # Send notification email to default admin email address
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL])

        # Delete the user account from the database
        user.delete()

        return Response({"message": "Account deleted and notification sent."}, status=200)

    except Exception as e:
        # Log and return an error if deletion or email sending fails
        print("Delete error:", e)
        return Response({"error": "Failed to delete account."}, status=500)
