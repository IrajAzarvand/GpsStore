from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
from apps.products.models import Product
from .models import Cart, CartItem


def get_or_create_cart(request):
    """
    Get or create cart for current user/session
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart


def cart_detail(request):
    """
    Display cart contents
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'total_price': cart.get_total_price(),
        'total_items': cart.get_total_items(),
    }
    return render(request, 'cart/cart.html', context)


@require_POST
def cart_add(request, product_id):
    """
    Add product to cart
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    if not product.is_in_stock():
        messages.error(request, _('این محصول موجود نیست.'))
        return redirect('products:product_detail', slug=product.slug)

    cart = get_or_create_cart(request)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'total_items': cart.get_total_items(),
            'message': _('محصول به سبد خرید اضافه شد.')
        })

    messages.success(request, _('محصول به سبد خرید اضافه شد.'))
    return redirect('cart:cart_detail')


@require_POST
def cart_update(request, product_id):
    """
    Update cart item quantity
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = get_or_create_cart(request)

    try:
        cart_item = CartItem.objects.get(cart=cart, product=product)
        quantity = int(request.POST.get('quantity', 1))

        if quantity <= 0:
            cart_item.delete()
        else:
            cart_item.quantity = min(quantity, product.stock_quantity)
            cart_item.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'total_price': cart.get_total_price(),
                'total_items': cart.get_total_items(),
                'item_total': cart_item.get_total_price() if quantity > 0 else 0,
            })

    except CartItem.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': _('آیتم در سبد خرید یافت نشد.')})

    return redirect('cart:cart_detail')


@require_POST
def cart_remove(request, product_id):
    """
    Remove product from cart
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = get_or_create_cart(request)

    try:
        cart_item = CartItem.objects.get(cart=cart, product=product)
        cart_item.delete()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'total_price': cart.get_total_price(),
                'total_items': cart.get_total_items(),
                'message': _('محصول از سبد خرید حذف شد.')
            })

        messages.success(request, _('محصول از سبد خرید حذف شد.'))

    except CartItem.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': _('آیتم در سبد خرید یافت نشد.')})

    return redirect('cart:cart_detail')
