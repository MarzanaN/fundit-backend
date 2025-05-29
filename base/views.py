from django.views.generic import View
from django.http import HttpResponse
from django.conf import settings
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import force_str
import logging
from rest_framework.decorators import api_view, action, permission_classes
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from decimal import Decimal, InvalidOperation
from .services import update_goal_with_history, create_guest_user
from django.contrib.auth import logout
from django.core.management import call_command
import os


from .models import (
     Budget, Expense, General_Saving, History, Income, Repayment_Goal,
     Savings_Goal
)

from .serializers import (
    BudgetSerializer, CustomUserSerializer, 
    ExpenseSerializer, GeneralSavingSerializer, HistorySerializer,
    IncomeSerializer, LoginSerializer, RegisterSerializer,
    RepaymentGoalSerializer, SavingsGoalSerializer, SettingsSerializer
)



logger = logging.getLogger(__name__)
User = get_user_model()


class FrontendAppView(View):
    def get(self, request):
        index_path = os.path.join(settings.REACT_BUILD_DIR, 'index.html')
        print("Looking for index.html at:", os.path.abspath(index_path))
        try:
            with open(index_path, encoding='utf-8') as f:
                return HttpResponse(f.read(), content_type='text/html')
        except FileNotFoundError:
            print("File not found at path:", os.path.abspath(index_path))
            return HttpResponse(
                "<h1>index.html not found</h1><p>Did you forget to run <code>npm run build</code> in the frontend?</p>",
                status=501,
                content_type='text/html'
            )


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        user.is_active = False
        user.save()

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        activation_link = f"{settings.SITE_URL}/api/activate/{uid}/{token}/"

        subject = 'Activate Your Fundit Account'
        message = (
            f'Hello {user.first_name or "there"},\n\n'
            f'Please click the link below to verify your email and activate your account:\n\n'
            f'{activation_link}\n\n'
            'If you did not sign up for Fundit, ignore this email.'
        )

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False
            )
            print("✅ Email sent to:", user.email)
        except Exception as e:
            print(f"❌ Email sending failed: {e}")



class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid activation link.'}, status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            return Response({'message': 'Account successfully activated.'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)



class LoginView(APIView):
    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            email = serializer.validated_data['email']
            password = serializer.validated_data['password']

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({'detail': 'Email not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not user.check_password(password):
                return Response({'detail': 'Incorrect password.'}, status=status.HTTP_401_UNAUTHORIZED)

            if not user.is_active:
                return Response({'detail': 'Account is not activated. Please check your email.'},
                                status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': CustomUserSerializer(user).data
            })

        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'detail': 'Email is required.'}, status=400)

        try:
            user = User.objects.get(email=email)

            if not user.is_active:
                return Response({'detail': 'Account is not activated. Please check your email.'}, status=403)

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

            subject = 'Reset Your Fundit Password'
            message = (
                f'Hello {user.first_name or "there"},\n\n'
                f'You requested a password reset. Click the link below to reset your password:\n\n'
                f'{reset_link}\n\n'
                'If you didn’t request this, you can safely ignore it.'
            )

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False
            )
            print("✅ Password reset email sent to:", user.email)

            return Response({'detail': 'Password reset email sent.'})

        except User.DoesNotExist:
            return Response({'detail': 'No user with that email.'}, status=404)
    

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not uidb64 or not token or not new_password:
            return Response({'detail': 'Missing parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'detail': 'Invalid user.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'detail': 'Password has been reset successfully.'})
    

class GetUserEmailView(APIView):
    def post(self, request):
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'detail': 'Invalid link'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'email': user.email}, status=status.HTTP_200_OK)



class VerifyResetTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'detail': 'Invalid link.'}, status=400)

        if default_token_generator.check_token(user, token):
            return Response({'email': user.email}, status=200)
        else:
            return Response({'detail': 'Token is invalid or expired.'}, status=400)


class UserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = CustomUserSerializer(user)
        return Response(serializer.data)


class UpdateSettingsView(generics.UpdateAPIView):
    serializer_class = SettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    

@api_view(['POST'])
def support_request(request):
    name = request.data.get('name')
    email = request.data.get('email')
    issue_type = request.data.get('issue_type')
    message = request.data.get('message')

    if not all([name, email, issue_type, message]):
        return Response({"error": "All fields are required."}, status=400)

    subject = f"Support Request: {issue_type.capitalize()} from {name}"
    full_message = f"From: {name} <{email}>\n\nIssue: {issue_type}\n\nMessage:\n{message}"

    try:
        send_mail(subject, full_message, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL])
        return Response({"message": "Support request sent successfully."}, status=200)
    except Exception as e:
        print("Email error:", e)
        return Response({"error": "Failed to send email."}, status=500)


class IncomeCreateView(generics.CreateAPIView):
    serializer_class = IncomeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UpdateIncomeEntriesViewSet(viewsets.ModelViewSet):
    serializer_class = IncomeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['date', 'category']
    ordering_fields = ['date', 'amount']

    def get_queryset(self):
        user = self.request.user
        queryset = Income.objects.filter(user=user)

        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(date__year=year)

        month = self.request.query_params.get('month')
        if month:
            try:
                year_m, month_num = month.split('-')
                start_date = parse_date(f"{year_m}-{month_num}-01")
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year_m)+1}-01-01")
                else:
                    end_date = parse_date(f"{year_m}-{int(month_num)+1}-01")

                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date) |
                        Q(recurring_monthly='yes', date__lte=end_date)
                    )
            except (ValueError, TypeError):
                pass

        return queryset.order_by('date')


class ExpenseCreateView(generics.CreateAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UpdateExpenseEntriesViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'date']

    def get_queryset(self):
        user = self.request.user
        queryset = Expense.objects.filter(user=user)

        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(date__year=year)

        month = self.request.query_params.get('month')
        if month:
            try:
                year_m, month_num = month.split('-')
                start_date = parse_date(f"{year_m}-{month_num}-01")
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year_m)+1}-01-01")
                else:
                    end_date = parse_date(f"{year_m}-{int(month_num)+1}-01")

                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date) |
                        Q(recurring_monthly='yes', date__lte=end_date)
                    )
            except (ValueError, TypeError):
                pass

        return queryset.order_by('date')


class BudgetCreateView(generics.CreateAPIView):
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UpdateBudgetEntriesViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'date']

    def get_queryset(self):
        user = self.request.user
        queryset = Budget.objects.filter(user=user)

        month = self.request.query_params.get('month')
        if month:
            try:
                year, month_num = month.split('-')
                start_date = parse_date(f"{year}-{month_num}-01")
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year) + 1}-01-01")
                else:
                    end_date = parse_date(f"{year}-{int(month_num) + 1}-01")

                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date) |
                        Q(recurring_monthly='yes', date__lte=end_date)
                    )
            except (ValueError, TypeError):
                pass

        return queryset.order_by('date', 'category')
    

class GeneralSavingsCreateView(generics.CreateAPIView):
    serializer_class = GeneralSavingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UpdateGeneralSavingsEntriesViewSet(viewsets.ModelViewSet):
    queryset = General_Saving.objects.all()
    serializer_class = GeneralSavingSerializer
    permission_classes = [IsAuthenticated]
    goal_field = 'amount'  

    def get_queryset(self):
        user = self.request.user
        queryset = General_Saving.objects.filter(user=user)

        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(date__year=year)

        month = self.request.query_params.get('month')
        if month:
            try:
                year_m, month_num = month.split('-')
                start_date = parse_date(f"{year_m}-{month_num}-01")
                if int(month_num) == 12:
                    end_date = parse_date(f"{int(year_m)+1}-01-01")
                else:
                    end_date = parse_date(f"{year_m}-{int(month_num)+1}-01")

                if start_date and end_date:
                    queryset = queryset.filter(
                        Q(date__gte=start_date, date__lt=end_date)
                    )
            except (ValueError, TypeError):
                pass

        return queryset.order_by('date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
       
    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        try:
            goal = self.get_object()
            action_type = request.data.get('action')
            amount_str = request.data.get('amount')
            date_str = request.data.get('date')

            try:
                amount = Decimal(amount_str)
            except (TypeError, ValueError, InvalidOperation):
                return Response({'error': 'Invalid amount'}, status=400)

            if date_str and len(date_str) == 7:
                date_str += '-15'
            date = parse_date(date_str)
            if date is None:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

            update_goal_with_history(goal, self.goal_field, action_type, amount, date)

            return Response({'status': f'{self.goal_field} updated'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    

class SavingsGoalCreateView(generics.CreateAPIView):
    serializer_class = SavingsGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RepaymentsGoalCreateView(generics.CreateAPIView):
    serializer_class = RepaymentGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BaseGoalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    goal_field = 'current_amount'  

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        try:
            goal = self.get_object()
            action_type = request.data.get('action')
            amount_str = request.data.get('amount')
            date_str = request.data.get('date')

            try:
                amount = Decimal(amount_str)
            except (TypeError, ValueError, InvalidOperation):
                return Response({'error': 'Invalid amount'}, status=400)

            if date_str and len(date_str) == 7:
                date_str += '-15'
            date = parse_date(date_str)
            if date is None:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

            update_goal_with_history(goal, self.goal_field, action_type, amount, date)

            return Response({'status': f'{self.goal_field} updated'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateSavingsGoalsViewSet(BaseGoalViewSet):
    queryset = Savings_Goal.objects.all()
    serializer_class = SavingsGoalSerializer
    goal_field = 'current_amount'


class UpdateRepaymentGoalsViewSet(BaseGoalViewSet):
    queryset = Repayment_Goal.objects.all()
    serializer_class = RepaymentGoalSerializer
    goal_field = 'current_amount'


class GeneralSavingHistoryListView(generics.ListAPIView):
    serializer_class = HistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        general_saving_id = self.kwargs.get('pk')  

        content_type = ContentType.objects.get(app_label='base', model='general_saving')
        
        return History.objects.filter(
            content_type=content_type,
            object_id=general_saving_id
        ).order_by('-date')


class SavingsGoalHistoryListView(generics.ListAPIView):
    serializer_class = HistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        general_saving_id = self.kwargs.get('pk')  

        content_type = ContentType.objects.get(app_label='base', model='savings_goal')
        
        return History.objects.filter(
            content_type=content_type,
            object_id=general_saving_id
        ).order_by('-date')


class RepaymentGoalHistoryListView(generics.ListAPIView):
    serializer_class = HistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        general_saving_id = self.kwargs.get('pk')  # 'pk' from URL pattern

        content_type = ContentType.objects.get(app_label='base', model='repayment_goal')
        
        return History.objects.filter(
            content_type=content_type,
            object_id=general_saving_id
        ).order_by('-date')
    

class GuestLoginView(APIView):
    def post(self, request):
        try:
            guest_user = create_guest_user()
            refresh = RefreshToken.for_user(guest_user)

            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': CustomUserSerializer(guest_user).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def logout_view(request):
    user = request.user
    logout(request)
    if getattr(user, 'is_guest', False):
        user.delete()
    return Response({'message': 'Logged out'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])  
def cleanup_old_guests(request):
    try:
        call_command('delete_old_guests')
        return Response({'message': 'Old guest users cleanup completed.'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    


class ChangePasswordView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response({'detail': 'Please provide current and new password.'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            return Response({'detail': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 6:
            return Response({'detail': 'New password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'detail': 'Password updated successfully!'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account_request(request):
    user = request.user
    delete_reason = request.data.get('delete_reason')
    other_reason = request.data.get('other_reason', '')
    comments = request.data.get('comments', '')
    rating = request.data.get('rating')
    confirm = request.data.get('confirm')

    if confirm is not True:
        return Response({"error": "Please confirm account deletion."}, status=400)

    if not delete_reason:
        return Response({"error": "Please provide a reason for deletion."}, status=400)

    if rating is None:
        return Response({"error": "Please provide a satisfaction rating."}, status=400)

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return Response({"error": "Rating must be between 1 and 5."}, status=400)
    except (ValueError, TypeError):
        return Response({"error": "Invalid rating format."}, status=400)

    final_reason = delete_reason
    if delete_reason == "Other":
        if not other_reason.strip():
            return Response({"error": "Please specify your reason."}, status=400)
        final_reason = f"Other: {other_reason}"

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
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL])

        user.delete()

        return Response({"message": "Account deleted and notification sent."}, status=200)

    except Exception as e:
        print("Delete error:", e)
        return Response({"error": "Failed to delete account."}, status=500)
