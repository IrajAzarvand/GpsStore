// GPS Store Interactive JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all interactive features
    initializeFadeIn();
    initializeSearch();
    initializeFilters();
    initializeImageSlider();
    initializeImageZoom();
    initializeProductModal();
    initializeFormValidation();
    initializeLazyLoading();
    initializeAnimations();
    initializeCartOperations();
    initializePerformanceOptimizations();
});

// Performance optimizations
function initializePerformanceOptimizations() {
    // Debounce scroll events
    let scrollTimeout;
    window.addEventListener('scroll', function() {
        if (!scrollTimeout) {
            scrollTimeout = setTimeout(function() {
                // Handle scroll-based features
                handleScrollOptimizations();
                scrollTimeout = null;
            }, 16); // ~60fps
        }
    });

    // Optimize resize events
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(handleResizeOptimizations, 100);
    });

    // Preload critical resources
    preloadCriticalResources();
}

function handleScrollOptimizations() {
    // Throttle scroll-based animations
    const fadeElements = document.querySelectorAll('.fade-in:not(.visible)');
    fadeElements.forEach(element => {
        const rect = element.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.8) {
            element.classList.add('visible');
        }
    });
}

function handleResizeOptimizations() {
    // Recalculate positions for modals and overlays on resize
    const modals = document.querySelectorAll('.product-modal, .image-zoom-modal');
    modals.forEach(modal => {
        // Force reflow for better performance
        modal.style.display = 'block';
        setTimeout(() => modal.style.display = '', 0);
    });
}

function preloadCriticalResources() {
    // Preload critical images
    const criticalImages = document.querySelectorAll('img[loading="eager"]');
    criticalImages.forEach(img => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = img.src;
        document.head.appendChild(link);
    });

    // Preload critical fonts
    const fontLink = document.createElement('link');
    fontLink.rel = 'preload';
    fontLink.as = 'font';
    fontLink.type = 'font/woff2';
    fontLink.href = '/static/fonts/Vazir-Regular.woff2';
    fontLink.crossOrigin = 'anonymous';
    document.head.appendChild(fontLink);
}

// Fade-in animation for elements
function initializeFadeIn() {
    const fadeElements = document.querySelectorAll('.fade-in');

    const fadeInObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.1 });

    fadeElements.forEach(element => {
        fadeInObserver.observe(element);
    });
}

// Real-time search functionality
function initializeSearch() {
    const searchInput = document.querySelector('.search-box input');
    if (!searchInput) return;

    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();

        if (query.length < 2) {
            // Hide search results if query is too short
            hideSearchResults();
            return;
        }

        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    // Hide search results when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target)) {
            hideSearchResults();
        }
    });
}

function performSearch(query) {
    fetch(`/api/products/search/?q=${encodeURIComponent(query)}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        displaySearchResults(data.results, query);
    })
    .catch(error => {
        console.error('Search error:', error);
    });
}

function displaySearchResults(results, query) {
    hideSearchResults();

    if (results.length === 0) return;

    const searchBox = document.querySelector('.search-box');
    const resultsDiv = document.createElement('div');
    resultsDiv.className = 'search-results';
    resultsDiv.innerHTML = `
        <div class="search-results-header">
            <span>${results.length} نتیجه برای "${query}"</span>
        </div>
        ${results.map(product => `
            <a href="${product.url}" class="search-result-item">
                <div class="search-result-image">
                    <img src="${product.image || '/static/images/no-image.png'}" alt="${product.name}">
                </div>
                <div class="search-result-info">
                    <h6>${product.name}</h6>
                    <span class="price">${product.price} تومان</span>
                </div>
            </a>
        `).join('')}
    `;

    searchBox.appendChild(resultsDiv);
}

function hideSearchResults() {
    const existing = document.querySelector('.search-results');
    if (existing) existing.remove();
}

// Dynamic filters for products
function initializeFilters() {
    const filterForm = document.querySelector('form[method="get"]');
    if (!filterForm) return;

    // Handle category filter
    const categorySelect = document.getElementById('category');
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            updateFilters();
        });
    }

    // Handle price range slider
    const priceRange = document.getElementById('price-range');
    if (priceRange) {
        priceRange.addEventListener('input', function() {
            updatePriceDisplay();
            updateFilters();
        });
    }

    // Handle sort select
    const sortSelect = document.getElementById('sort');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            updateFilters();
        });
    }
}

function updatePriceDisplay() {
    const priceRange = document.getElementById('price-range');
    const priceMax = document.getElementById('price-max');
    if (priceRange && priceMax) {
        const value = parseInt(priceRange.value);
        priceMax.textContent = value.toLocaleString('fa-IR');
    }
}

function updateFilters() {
    const filterForm = document.querySelector('form[method="get"]');
    if (!filterForm) return;

    const formData = new FormData(filterForm);
    const params = new URLSearchParams();

    for (let [key, value] of formData.entries()) {
        if (value && value !== '') {
            params.append(key, value);
        }
    }

    // Update URL without page reload
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);

    // Reload products via AJAX
    loadFilteredProducts(params);
}

function loadFilteredProducts(params) {
    const productsContainer = document.querySelector('.row .col-lg-9');
    if (!productsContainer) return;

    // Show loading state
    productsContainer.innerHTML = '<div class="text-center py-5"><div class="spinner-border" role="status"></div></div>';

    fetch(`${window.location.pathname}?${params.toString()}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.text())
    .then(html => {
        // Extract products section from response
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newProducts = doc.querySelector('.row .col-lg-9');
        if (newProducts) {
            productsContainer.innerHTML = newProducts.innerHTML;
            // Re-initialize features for new content
            initializeFadeIn();
            initializeImageSlider();
            initializeLazyLoading();
        }
    })
    .catch(error => {
        console.error('Filter error:', error);
        productsContainer.innerHTML = '<div class="text-center py-5"><p class="text-danger">خطا در بارگذاری محصولات</p></div>';
    });
}

// Product image slider
function initializeImageSlider() {
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => {
        const images = card.querySelectorAll('.card-img-top');
        if (images.length > 1) {
            createImageSlider(card, images);
        }
    });
}

function createImageSlider(card, images) {
    let currentIndex = 0;
    const imgContainer = card.querySelector('.card-img-top').parentElement;

    // Create navigation arrows
    const prevBtn = document.createElement('button');
    prevBtn.className = 'slider-arrow slider-prev';
    prevBtn.innerHTML = '‹';
    prevBtn.onclick = () => changeImage(-1);

    const nextBtn = document.createElement('button');
    nextBtn.className = 'slider-arrow slider-next';
    nextBtn.innerHTML = '›';
    nextBtn.onclick = () => changeImage(1);

    // Create dots indicator
    const dotsContainer = document.createElement('div');
    dotsContainer.className = 'slider-dots';

    images.forEach((_, index) => {
        const dot = document.createElement('span');
        dot.className = `slider-dot ${index === 0 ? 'active' : ''}`;
        dot.onclick = () => goToImage(index);
        dotsContainer.appendChild(dot);
    });

    imgContainer.style.position = 'relative';
    imgContainer.appendChild(prevBtn);
    imgContainer.appendChild(nextBtn);
    imgContainer.appendChild(dotsContainer);

    const dots = dotsContainer.querySelectorAll('.slider-dot');

    function changeImage(direction) {
        currentIndex = (currentIndex + direction + images.length) % images.length;
        updateSlider();
    }

    function goToImage(index) {
        currentIndex = index;
        updateSlider();
    }

    function updateSlider() {
        images.forEach((img, index) => {
            img.style.display = index === currentIndex ? 'block' : 'none';
        });
        dots.forEach((dot, index) => {
            dot.classList.toggle('active', index === currentIndex);
        });
    }

    updateSlider();
}

// Image zoom functionality
function initializeImageZoom() {
    const productImages = document.querySelectorAll('.product-image img, #main-product-image');
    productImages.forEach(img => {
        img.addEventListener('click', function() {
            openImageZoom(this.src, this.alt);
        });
    });
}

function openImageZoom(src, alt) {
    const modal = document.createElement('div');
    modal.className = 'image-zoom-modal';
    modal.innerHTML = `
        <div class="image-zoom-overlay" onclick="closeImageZoom()"></div>
        <div class="image-zoom-container">
            <img src="${src}" alt="${alt}" class="image-zoom-img">
            <button class="image-zoom-close" onclick="closeImageZoom()">×</button>
        </div>
    `;
    document.body.appendChild(modal);

    // Add zoom functionality
    const zoomImg = modal.querySelector('.image-zoom-img');
    let scale = 1;
    let isDragging = false;
    let startX, startY, translateX = 0, translateY = 0;

    zoomImg.addEventListener('wheel', function(e) {
        e.preventDefault();
        scale += e.deltaY * -0.01;
        scale = Math.min(Math.max(1, scale), 3);
        updateZoom();
    });

    zoomImg.addEventListener('mousedown', function(e) {
        isDragging = true;
        startX = e.clientX - translateX;
        startY = e.clientY - translateY;
    });

    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;
        updateZoom();
    });

    document.addEventListener('mouseup', function() {
        isDragging = false;
    });

    function updateZoom() {
        zoomImg.style.transform = `scale(${scale}) translate(${translateX}px, ${translateY}px)`;
    }
}

function closeImageZoom() {
    const modal = document.querySelector('.image-zoom-modal');
    if (modal) modal.remove();
}

// Product modal functionality
function initializeProductModal() {
    const productLinks = document.querySelectorAll('.product-card a[href*="product"]');
    productLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.href;
            openProductModal(url);
        });
    });
}

function openProductModal(url) {
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.text())
    .then(html => {
        const modal = document.createElement('div');
        modal.className = 'product-modal';
        modal.innerHTML = `
            <div class="product-modal-overlay" onclick="closeProductModal()"></div>
            <div class="product-modal-container">
                <div class="product-modal-content">
                    ${extractProductContent(html)}
                </div>
                <button class="product-modal-close" onclick="closeProductModal()">×</button>
            </div>
        `;
        document.body.appendChild(modal);

        // Re-initialize features in modal
        initializeImageSlider();
        initializeImageZoom();
        initializeFormValidation();
    })
    .catch(error => {
        console.error('Modal error:', error);
    });
}

function extractProductContent(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const content = doc.querySelector('.container');
    return content ? content.innerHTML : html;
}

function closeProductModal() {
    const modal = document.querySelector('.product-modal');
    if (modal) modal.remove();
}

// Form validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });

        // Real-time validation
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const inputs = form.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        if (!validateField(input)) {
            isValid = false;
        }
    });

    return isValid;
}

function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let message = '';

    // Remove existing error messages
    const existingError = field.parentElement.querySelector('.field-error');
    if (existingError) existingError.remove();

    // Basic validation rules
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        message = 'این فیلد اجباری است';
    } else if (field.type === 'email' && value && !isValidEmail(value)) {
        isValid = false;
        message = 'ایمیل معتبر نیست';
    } else if (field.type === 'number') {
        const min = field.getAttribute('min');
        const max = field.getAttribute('max');
        const numValue = parseFloat(value);

        if (min && numValue < parseFloat(min)) {
            isValid = false;
            message = `حداقل مقدار ${min} است`;
        } else if (max && numValue > parseFloat(max)) {
            isValid = false;
            message = `حداکثر مقدار ${max} است`;
        }
    }

    // Show error message
    if (!isValid) {
        field.classList.add('is-invalid');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error text-danger small';
        errorDiv.textContent = message;
        field.parentElement.appendChild(errorDiv);
    } else {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
    }

    return isValid;
}

function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Lazy loading for images with performance optimizations
function initializeLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    loadImage(img);
                    imageObserver.unobserve(img);
                }
            });
        }, {
            rootMargin: '50px 0px', // Start loading 50px before the image enters the viewport
            threshold: 0.01
        });

        images.forEach(img => imageObserver.observe(img));
    } else {
        // Fallback for browsers without IntersectionObserver
        images.forEach(img => loadImage(img));
    }
}

function loadImage(img) {
    const src = img.dataset.src;
    if (!src) return;

    // Create a new image to preload
    const newImg = new Image();
    newImg.onload = function() {
        img.src = src;
        img.classList.remove('lazy');
        img.classList.add('loaded');
    };
    newImg.onerror = function() {
        // Fallback to a default image
        img.src = '/static/images/no-image.png';
        img.classList.remove('lazy');
    };
    newImg.src = src;
}

// Additional animations and effects
function initializeAnimations() {
    // Add pulse effect to buttons on hover
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.classList.add('pulse');
        });
        btn.addEventListener('mouseleave', function() {
            this.classList.remove('pulse');
        });
    });

    // Add loading animation to forms on submit
    const submitButtons = document.querySelectorAll('button[type="submit"], input[type="submit"]');
    submitButtons.forEach(btn => {
        btn.closest('form').addEventListener('submit', function() {
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>در حال ارسال...';
            btn.disabled = true;
        });
    });
}

// Enhanced cart operations
function initializeCartOperations() {
    // This is already handled in individual templates, but we can add global enhancements here
    // For example, cart counter updates across pages
    updateCartCounter();
}

function updateCartCounter() {
    // This function can be called after cart operations to update counter globally
    const cartCounter = document.getElementById('cart-counter');
    if (cartCounter && window.cartTotalItems !== undefined) {
        cartCounter.textContent = window.cartTotalItems;
    }
}

// Utility function for showing messages (used across the app)
function showMessage(message, type = 'info') {
    // Remove existing messages
    const existingMessages = document.querySelectorAll('.alert');
    existingMessages.forEach(msg => msg.remove());

    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} alert-dismissible fade show position-fixed`;
    messageEl.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    messageEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(messageEl);

    // Auto remove after 3 seconds
    setTimeout(() => {
        if (messageEl.parentElement) {
            messageEl.remove();
        }
    }, 3000);
}

// Make functions globally available
window.showMessage = showMessage;
window.closeImageZoom = closeImageZoom;
window.closeProductModal = closeProductModal;

// Performance monitoring
function initializePerformanceMonitoring() {
    // Monitor Core Web Vitals
    if ('web-vitals' in window) {
        // These would be loaded from a CDN in production
        // webVitals.getCLS(console.log);
        // webVitals.getFID(console.log);
        // webVitals.getFCP(console.log);
        // webVitals.getLCP(console.log);
        // webVitals.getTTFB(console.log);
    }

    // Monitor memory usage
    if ('memory' in performance) {
        setInterval(() => {
            const memInfo = performance.memory;
            console.log(`Memory: ${Math.round(memInfo.usedJSHeapSize / 1048576)}MB used of ${Math.round(memInfo.totalJSHeapSize / 1048576)}MB`);
        }, 10000);
    }

    // Monitor long tasks
    if ('PerformanceObserver' in window) {
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (entry.duration > 50) { // Tasks longer than 50ms
                    console.warn('Long task detected:', entry);
                }
            }
        });
        observer.observe({ entryTypes: ['longtask'] });
    }
}

// Initialize performance monitoring
initializePerformanceMonitoring();