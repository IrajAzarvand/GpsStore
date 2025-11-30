from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import Product, Category, ProductImage, Review


class HomeView(TemplateView):
    """
    Home page view
    """
    template_name = 'home.html'

    @method_decorator(cache_page(300))  # Cache for 5 minutes
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Cache key for featured products
        cache_key = 'home_featured_products'
        featured_products = cache.get(cache_key)

        if featured_products is None:
            # Use select_related and prefetch_related for optimization
            featured_products = Product.objects.filter(
                is_active=True,
                is_featured=True
            ).select_related('category').prefetch_related(
                Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
            )[:6]
            cache.set(cache_key, featured_products, 300)  # Cache for 5 minutes

        context['featured_products'] = featured_products

        # Cache key for categories
        cache_key_categories = 'home_categories'
        categories = cache.get(cache_key_categories)

        if categories is None:
            categories = Category.objects.filter(is_active=True)
            cache.set(cache_key_categories, categories, 600)  # Cache for 10 minutes

        context['categories'] = categories

        return context


class ProductListView(ListView):
    """
    Product listing view with filtering
    """
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        # Use select_related for category and prefetch_related for images
        queryset = Product.objects.filter(is_active=True).select_related('category').prefetch_related(
            Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
        )

        # Category filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Search filter
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(short_description__icontains=search_query)
            )

        # Price range filter
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        # Sorting
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by in ['name', '-name', 'price', '-price', 'created_at', '-created_at']:
            queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter options
        context['categories'] = Category.objects.filter(is_active=True)
        context['current_category'] = self.request.GET.get('category')
        context['search_query'] = self.request.GET.get('q')
        context['min_price'] = self.request.GET.get('min_price')
        context['max_price'] = self.request.GET.get('max_price')
        context['sort_by'] = self.request.GET.get('sort', '-created_at')

        return context

    def render_to_response(self, context, **response_kwargs):
        """Override to support AJAX requests"""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return only the products section for AJAX requests
            products_html = render_to_string('products/_product_list.html', context, request=self.request)
            return JsonResponse({'html': products_html})
        return super().render_to_response(context, **response_kwargs)


class ProductDetailView(DetailView):
    """
    Product detail view
    """
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related('category').prefetch_related(
            Prefetch('images', queryset=ProductImage.objects.all()),
            Prefetch('reviews', queryset=Review.objects.select_related('user'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()

        # Cache key for related products
        cache_key = f'related_products_{product.category_id}_{product.pk}'
        related_products = cache.get(cache_key)

        if related_products is None:
            # Related products (same category) with optimization
            related_products = Product.objects.filter(
                category=product.category,
                is_active=True
            ).exclude(pk=product.pk).select_related('category').prefetch_related(
                Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
            )[:4]
            cache.set(cache_key, related_products, 600)  # Cache for 10 minutes

        context['related_products'] = related_products

        # Product images are already prefetched in get_queryset
        context['product_images'] = product.images.all()

        return context

    def render_to_response(self, context, **response_kwargs):
        """Override to support AJAX requests for product detail modal"""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return the full product detail template for modal
            product_html = render_to_string('products/product_detail.html', context, request=self.request)
            return JsonResponse({'html': product_html})
        return super().render_to_response(context, **response_kwargs)


class ProductSearchView(TemplateView):
    """
    AJAX search view for real-time product search
    """
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        results = []

        if len(query) >= 2:
            products = Product.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(short_description__icontains=query) |
                Q(sku__icontains=query),
                is_active=True
            )[:5]  # Limit to 5 results for performance

            results = [{
                'name': product.name,
                'url': product.get_absolute_url(),
                'image': product.images.first().image.url if product.images.exists() else None,
                'price': product.get_discounted_price()
            } for product in products]

        return JsonResponse({'results': results})


class CategoryListView(ListView):
    """
    Category listing view
    """
    model = Category
    template_name = 'products/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(is_active=True)


class CategoryDetailView(DetailView):
    """
    Category detail view
    """
    model = Category
    template_name = 'products/category_detail.html'
    context_object_name = 'category'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Category.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_object()

        # Products in this category
        context['products'] = Product.objects.filter(
            category=category,
            is_active=True
        )

        # Subcategories if any
        context['subcategories'] = category.subcategories.filter(is_active=True)

        return context
