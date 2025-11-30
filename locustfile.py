from locust import HttpUser, task, between
import random
from decimal import Decimal


class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Setup before starting tasks"""
        self.client.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    @task(3)
    def view_homepage(self):
        """Visit homepage"""
        self.client.get("/")

    @task(2)
    def view_products(self):
        """Browse products"""
        self.client.get("/products/")

    @task(1)
    def view_product_detail(self):
        """View product details"""
        # Simulate viewing different products
        product_ids = [1, 2, 3, 4, 5]
        product_id = random.choice(product_ids)
        self.client.get(f"/products/product-{product_id}/")

    @task(1)
    def search_products(self):
        """Search for products"""
        search_terms = ["GPS", "tracker", "vehicle", "personal"]
        term = random.choice(search_terms)
        self.client.get(f"/products/?q={term}")

    @task(1)
    def view_cart(self):
        """View shopping cart"""
        self.client.get("/cart/")

    @task(1)
    def add_to_cart(self):
        """Add product to cart"""
        product_id = random.randint(1, 5)
        quantity = random.randint(1, 3)
        self.client.post(f"/cart/add/{product_id}/", {
            "quantity": quantity
        })

    @task(1)
    def view_api_products(self):
        """Test API endpoints"""
        self.client.get("/api/products/")

    @task(1)
    def view_tracking_page(self):
        """View GPS tracking page"""
        self.client.get("/tracking/")


class APITester(HttpUser):
    wait_time = between(0.5, 2)

    @task
    def api_products(self):
        """Test products API"""
        self.client.get("/api/products/")

    @task
    def api_product_detail(self):
        """Test product detail API"""
        product_id = random.randint(1, 10)
        self.client.get(f"/api/products/{product_id}/")

    @task
    def api_categories(self):
        """Test categories API"""
        self.client.get("/api/categories/")

    @task
    def api_tracking_data(self):
        """Test tracking API"""
        device_id = random.randint(1, 5)
        self.client.get(f"/api/devices/{device_id}/tracking/")


# Performance test configuration
# Run with: locust -f locustfile.py --host=http://127.0.0.1:8000
# Or for headless: locust -f locustfile.py --host=http://127.0.0.1:8000 --no-web -c 100 -r 10 --run-time 1m