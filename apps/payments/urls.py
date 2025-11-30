from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment initiation
    path('initiate/<int:order_id>/', views.initiate_payment, name='initiate_payment'),

    # Payment callbacks
    path('callback/', views.payment_callback, name='payment_callback'),

    # Payment status pages
    path('success/', views.payment_success, name='payment_success'),
    path('failed/', views.payment_failed, name='payment_failed'),

    # Card to card payment
    path('card-to-card/<int:order_id>/', views.card_to_card_payment, name='card_to_card_payment'),

    # Payment details
    path('detail/<int:payment_id>/', views.payment_detail, name='payment_detail'),

    # Payment actions
    path('retry/<int:payment_id>/', views.retry_payment, name='retry_payment'),

    # Webhooks
    path('webhook/', views.payment_webhook, name='payment_webhook'),
]