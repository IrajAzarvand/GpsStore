from django.contrib import admin
from .models import Payment, CardToCardTransfer, PaymentGatewayConfig


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_method', 'amount', 'status', 'payment_date', 'transaction_id')
    list_filter = ('payment_method', 'status', 'payment_date', 'created_at')
    search_fields = ('order__order_number', 'transaction_id', 'zarinpal_authority', 'ref_id')
    readonly_fields = ('created_at', 'updated_at', 'payment_date')

    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'amount')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'status', 'transaction_id', 'payment_date')
        }),
        ('Gateway Specific', {
            'fields': ('zarinpal_authority', 'bank_token', 'ref_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Payments should be created automatically, not manually
        return False


@admin.register(CardToCardTransfer)
class CardToCardTransferAdmin(admin.ModelAdmin):
    list_display = ('payment', 'payer_name', 'transfer_amount', 'status', 'transfer_date', 'expires_at')
    list_filter = ('status', 'transfer_date', 'verified_at')
    search_fields = ('payment__order__order_number', 'payer_name', 'payer_card_number')
    readonly_fields = ('created_at', 'verified_at')

    fieldsets = (
        ('Transfer Information', {
            'fields': ('payment', 'status')
        }),
        ('Payer Details', {
            'fields': ('payer_name', 'payer_card_number', 'transfer_amount', 'transfer_date')
        }),
        ('Verification', {
            'fields': ('description', 'receipt_image', 'admin_notes', 'verified_by', 'verified_at', 'expires_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_transfers', 'reject_transfers']

    def approve_transfers(self, request, queryset):
        for transfer in queryset.filter(status='pending'):
            transfer.approve(request.user)
        self.message_user(request, f"{queryset.count()} transfer(s) approved.")
    approve_transfers.short_description = "Approve selected transfers"

    def reject_transfers(self, request, queryset):
        for transfer in queryset.filter(status='pending'):
            transfer.reject(request.user, "Bulk rejection")
        self.message_user(request, f"{queryset.count()} transfer(s) rejected.")
    reject_transfers.short_description = "Reject selected transfers"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('payment__order', 'verified_by')


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'gateway_type', 'is_active', 'merchant_id', 'min_amount', 'max_amount')
    list_filter = ('gateway_type', 'is_active')
    search_fields = ('name', 'merchant_id')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'gateway_type', 'is_active')
        }),
        ('API Credentials', {
            'fields': ('merchant_id', 'api_key', 'api_secret'),
            'classes': ('collapse',)
        }),
        ('URLs', {
            'fields': ('callback_url', 'success_url', 'failure_url'),
            'classes': ('collapse',)
        }),
        ('Limits', {
            'fields': ('min_amount', 'max_amount', 'daily_limit')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
