import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from .models import Payment, PaymentGatewayConfig, CardToCardTransfer
from apps.orders.models import Order


@login_required
def initiate_payment(request, order_id):
    """
    Initiate payment for an order
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Check if order is in pending status
    if order.status != 'pending':
        messages.error(request, 'این سفارش قابل پرداخت نیست.')
        return redirect('orders:order_detail', order_id=order.id)

    # Check if payment already exists
    if hasattr(order, 'payment'):
        payment = order.payment
        if payment.status == 'completed':
            messages.info(request, 'این سفارش قبلاً پرداخت شده است.')
            return redirect('orders:order_detail', order_id=order.id)
    else:
        # Create payment record
        payment = Payment.objects.create(
            order=order,
            payment_method='zarinpal',  # Default to Zarinpal
            amount=order.get_final_total()
        )

    # Get payment gateway config
    try:
        gateway_config = PaymentGatewayConfig.objects.get(
            gateway_type='zarinpal',
            is_active=True
        )
    except PaymentGatewayConfig.DoesNotExist:
        messages.error(request, 'درگاه پرداخت فعال یافت نشد.')
        return redirect('orders:order_detail', order_id=order.id)

    # Check amount limits
    if payment.amount < gateway_config.min_amount or payment.amount > gateway_config.max_amount:
        messages.error(request, f'مبلغ پرداخت باید بین {gateway_config.min_amount:,} و {gateway_config.max_amount:,} تومان باشد.')
        return redirect('orders:order_detail', order_id=order.id)

    # Initiate payment with Zarinpal
    zarinpal_data = {
        'merchant_id': gateway_config.merchant_id,
        'amount': int(payment.amount * 100),  # Convert to Rials
        'description': f'پرداخت سفارش {order.order_number}',
        'callback_url': request.build_absolute_uri(reverse('payments:payment_callback')),
        'metadata': {
            'order_id': str(order.id),
            'payment_id': str(payment.id),
        }
    }

    try:
        response = requests.post(
            'https://api.zarinpal.com/pg/v4/payment/request.json',
            json=zarinpal_data,
            timeout=30
        )
        response_data = response.json()

        if response_data.get('data') and response_data['data'].get('code') == 100:
            authority = response_data['data']['authority']
            payment.zarinpal_authority = authority
            payment.save()

            # Redirect to Zarinpal payment page
            payment_url = f'https://www.zarinpal.com/pg/StartPay/{authority}'
            return redirect(payment_url)
        else:
            error_message = response_data.get('errors', {}).get('message', 'خطا در اتصال به درگاه پرداخت')
            messages.error(request, f'خطا در شروع پرداخت: {error_message}')
            payment.mark_failed()
            return redirect('orders:order_detail', order_id=order.id)

    except requests.RequestException as e:
        messages.error(request, f'خطا در اتصال به درگاه پرداخت: {str(e)}')
        payment.mark_failed()
        return redirect('orders:order_detail', order_id=order.id)


def payment_callback(request):
    """
    Handle payment callback from Zarinpal
    """
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    if not authority:
        return render(request, 'payments/payment_failed.html', {
            'error': 'شناسه پرداخت یافت نشد.'
        })

    try:
        payment = Payment.objects.get(zarinpal_authority=authority)
    except Payment.DoesNotExist:
        return render(request, 'payments/payment_failed.html', {
            'error': 'پرداخت یافت نشد.'
        })

    if status == 'OK':
        # Verify payment
        gateway_config = PaymentGatewayConfig.objects.filter(
            gateway_type='zarinpal',
            is_active=True
        ).first()

        if not gateway_config:
            return render(request, 'payments/payment_failed.html', {
                'error': 'تنظیمات درگاه پرداخت یافت نشد.'
            })

        verify_data = {
            'merchant_id': gateway_config.merchant_id,
            'authority': authority,
            'amount': int(payment.amount * 100)
        }

        try:
            response = requests.post(
                'https://api.zarinpal.com/pg/v4/payment/verify.json',
                json=verify_data,
                timeout=30
            )
            response_data = response.json()

            if response_data.get('data') and response_data['data'].get('code') == 100:
                ref_id = response_data['data']['ref_id']
                payment.ref_id = ref_id
                payment.mark_completed()

                # Update order status
                payment.order.status = 'confirmed'
                payment.order.save()

                return render(request, 'payments/payment_success.html', {
                    'payment': payment,
                    'ref_id': ref_id
                })
            else:
                payment.mark_failed()
                error_message = response_data.get('errors', {}).get('message', 'پرداخت تأیید نشد')
                return render(request, 'payments/payment_failed.html', {
                    'error': error_message,
                    'payment': payment
                })

        except requests.RequestException as e:
            payment.mark_failed()
            return render(request, 'payments/payment_failed.html', {
                'error': f'خطا در تأیید پرداخت: {str(e)}',
                'payment': payment
            })

    else:
        payment.mark_failed()
        return render(request, 'payments/payment_failed.html', {
            'error': 'پرداخت توسط کاربر لغو شد.',
            'payment': payment
        })


@login_required
def payment_detail(request, payment_id):
    """
    Show payment details
    """
    payment = get_object_or_404(Payment, id=payment_id, order__user=request.user)
    return render(request, 'payments/payment_detail.html', {
        'payment': payment
    })


@login_required
def card_to_card_payment(request, order_id):
    """
    Handle card-to-card payment submission
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method == 'POST':
        payer_name = request.POST.get('payer_name')
        card_number = request.POST.get('card_number')
        transfer_amount = request.POST.get('transfer_amount')
        transfer_date = request.POST.get('transfer_date')
        description = request.POST.get('description')
        receipt_image = request.FILES.get('receipt_image')

        # Validate card number format
        import re
        if not re.match(r'^\d{4}-\d{4}-\d{4}-\d{4}$', card_number):
            messages.error(request, 'فرمت شماره کارت صحیح نیست.')
            return redirect('payments:card_to_card_payment', order_id=order_id)

        # Create payment if not exists
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'payment_method': 'card_to_card',
                'amount': order.get_final_total()
            }
        )

        # Create card transfer record
        from django.utils.dateparse import parse_datetime
        transfer_datetime = parse_datetime(f"{transfer_date} 12:00:00")  # Default time

        CardToCardTransfer.objects.create(
            payment=payment,
            payer_name=payer_name,
            payer_card_number=card_number,
            transfer_amount=Decimal(transfer_amount),
            transfer_date=transfer_datetime,
            description=description,
            receipt_image=receipt_image,
            expires_at=timezone.now() + timezone.timedelta(days=2)  # 2 days expiry
        )

        messages.success(request, 'اطلاعات کارت به کارت شما ثبت شد. پس از تأیید توسط ادمین، سفارش شما پردازش خواهد شد.')
        return redirect('orders:order_detail', order_id=order.id)

    return render(request, 'payments/card_to_card.html', {
        'order': order
    })


@csrf_exempt
@require_POST
def payment_webhook(request):
    """
    Handle payment webhooks from gateways
    """
    # For now, just log the webhook data
    # In production, implement proper webhook handling for each gateway

    try:
        data = json.loads(request.body)
        # Process webhook data based on gateway type
        # This is a placeholder for webhook implementation

        return JsonResponse({'status': 'ok'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)


@login_required
def retry_payment(request, payment_id):
    """
    Retry a failed payment
    """
    payment = get_object_or_404(Payment, id=payment_id, order__user=request.user)

    if not payment.can_retry():
        messages.error(request, 'این پرداخت قابل تکرار نیست.')
        return redirect('payments:payment_detail', payment_id=payment.id)

    # Reset payment status
    payment.status = 'pending'
    payment.transaction_id = None
    payment.zarinpal_authority = None
    payment.save()

@login_required
def payment_success(request):
    """
    Show payment success page
    """
    return render(request, 'payments/payment_success.html')


@login_required
def payment_failed(request):
    """
    Show payment failed page
    """
    return render(request, 'payments/payment_failed.html')
    return redirect('payments:initiate_payment', order_id=payment.order.id)
