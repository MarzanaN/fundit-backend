from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, LoginView, UserView, UpdateSettingsView,
    PasswordResetRequestView, PasswordResetConfirmView,
    GetUserEmailView, VerifyResetTokenView, support_request,
    IncomeCreateView, UpdateIncomeEntriesViewSet, ExpenseCreateView,
    BudgetCreateView, UpdateExpenseEntriesViewSet, UpdateBudgetEntriesViewSet,
    GeneralSavingsCreateView, UpdateGeneralSavingsEntriesViewSet, 
    SavingsGoalCreateView, RepaymentsGoalCreateView, UpdateSavingsGoalsViewSet,
    UpdateRepaymentGoalsViewSet, GeneralSavingHistoryListView,
    SavingsGoalHistoryListView,
    RepaymentGoalHistoryListView, ChangePasswordView, 
    GuestLoginView, logout_view, delete_account_request, ActivateAccountView
)

router = DefaultRouter()
router.register(r'income', UpdateIncomeEntriesViewSet, basename='income')
router.register(r'expenses', UpdateExpenseEntriesViewSet, basename='expense')
router.register(r'budgets', UpdateBudgetEntriesViewSet, basename='budget')
router.register(r'general-savings', UpdateGeneralSavingsEntriesViewSet, basename='general-savings')
router.register(r'savings-goals', UpdateSavingsGoalsViewSet, basename='savings-goals')
router.register(r'repayment-goals', UpdateRepaymentGoalsViewSet, basename='repayment-goals')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('activate/<uidb64>/<token>/', ActivateAccountView.as_view(), name='activate-account'),
    path('login/', LoginView.as_view(), name='login'),
    path('guest-login/', GuestLoginView.as_view(), name='guest-login'),
    path('logout/', logout_view, name='logout'),
    path('user/', UserView.as_view(), name='user'),
    path('settings/update/', UpdateSettingsView.as_view(), name='update-settings'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('reset-password-confirm/', PasswordResetConfirmView.as_view()),
    path('settings/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('get-user-email/', GetUserEmailView.as_view()),
    path('verify-reset-token/<uidb64>/<token>/', VerifyResetTokenView.as_view()),
    path('support/', support_request),
    path('delete-account/', delete_account_request),
    path('income/add/', IncomeCreateView.as_view(), name='add-income'),
    path('expense/add/', ExpenseCreateView.as_view(), name='add-expense'),
    path('budget/add/', BudgetCreateView.as_view(), name='add-budget'),
    path('general-savings/add/', GeneralSavingsCreateView.as_view(), name='add-general-savings'),
    path('savings-goal/add/', SavingsGoalCreateView.as_view(), name='add-savings-goal'),
    path('repayments-goal/add/', RepaymentsGoalCreateView.as_view(), name='add-repayment-goals'),
    path('general-savings/<int:pk>/history/', GeneralSavingHistoryListView.as_view(), name='general-saving-history'),
    path('savings-goals/<int:pk>/history/', SavingsGoalHistoryListView.as_view(), name='savings-goal-history'),
    path('repayment-goals/<int:pk>/history/', RepaymentGoalHistoryListView.as_view(), name='repayment-goal-history'),
    path('', include(router.urls)),
    
]

