from django.contrib import admin
from .models import SubscriptionPlan, Subscription, PaymentRecord


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price_per_year', 'max_devices', 'billing_cycle', 'is_active')
    list_filter = ('plan_type', 'billing_cycle', 'is_active', 'real_time_updates', 'geofencing_alerts')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan_type', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price_per_year', 'price_per_month', 'billing_cycle', 'trial_days')
        }),
        ('Limits & Features', {
            'fields': ('max_devices', 'storage_days', 'real_time_updates', 'geofencing_alerts', 'sms_alerts', 'email_alerts', 'api_access')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'billing_cycle', 'start_date', 'end_date', 'days_remaining')
    list_filter = ('status', 'billing_cycle', 'plan__plan_type', 'auto_renew', 'start_date')
    search_fields = ('user__username', 'user__email', 'plan__name')
    readonly_fields = ('created_at', 'updated_at', 'days_remaining')

    fieldsets = (
        ('Subscription Details', {
            'fields': ('user', 'plan', 'status', 'billing_cycle', 'auto_renew')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'trial_end_date', 'next_billing_date')
        }),
        ('Devices', {
            'fields': ('devices',),
            'classes': ('collapse',)
        }),
        ('Billing', {
            'fields': ('last_payment_date', 'total_paid'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'days_remaining'),
            'classes': ('collapse',)
        }),
    )

    filter_horizontal = ('devices',)

    actions = ['activate_subscriptions', 'renew_subscriptions']

    def activate_subscriptions(self, request, queryset):
        for subscription in queryset.filter(status='trial'):
            subscription.activate()
        self.message_user(request, f"{queryset.count()} subscription(s) activated.")
    activate_subscriptions.short_description = "Activate selected subscriptions"

    def renew_subscriptions(self, request, queryset):
        for subscription in queryset.filter(status='active'):
            subscription.renew()
        self.message_user(request, f"{queryset.count()} subscription(s) renewed.")
    renew_subscriptions.short_description = "Renew selected subscriptions"

    def days_remaining(self, obj):
        return obj.days_remaining()
    days_remaining.short_description = 'Days Remaining'


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'payment_type', 'amount', 'currency', 'is_successful', 'payment_date')
    list_filter = ('payment_type', 'is_successful', 'payment_date', 'currency')
    search_fields = ('subscription__user__username', 'transaction_id', 'payment_method')
    readonly_fields = ('payment_date', 'effective_date')

    fieldsets = (
        ('Payment Information', {
            'fields': ('subscription', 'payment_type', 'amount', 'currency')
        }),
        ('Transaction Details', {
            'fields': ('transaction_id', 'payment_method', 'is_successful', 'failure_reason')
        }),
        ('Dates', {
            'fields': ('payment_date', 'effective_date'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Payment records should be created automatically
        return False
