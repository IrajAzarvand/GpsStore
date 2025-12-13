import requests
import logging
import time
from threading import Lock
from django.conf import settings
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class GeocodingProvider(ABC):
    @abstractmethod
    def get_address(self, lat, lon):
        pass

class NominatimProvider(GeocodingProvider):
    def __init__(self):
        self.base_url = settings.NOMINATIM_BASE_URL
        self.last_request_time = 0
        self.lock = Lock()
        self.min_interval = 1.1  # 1.1 seconds to be safe (limit is 1/sec)

    def get_address(self, lat, lon):
        # Enforce rate limiting specifically for public Nominatim
        if 'nominatim.openstreetmap.org' in self.base_url:
            with self.lock:
                current_time = time.time()
                elapsed = current_time - self.last_request_time
                if elapsed < self.min_interval:
                    time.sleep(self.min_interval - elapsed)
                self.last_request_time = time.time()

        try:
            headers = {
                'User-Agent': 'GpsStore/1.0 (contact@bruna.ir)' # Required by Nominatim Policy
            }
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'accept-language': 'fa' # Persian response
            }
            response = requests.get(self.base_url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get('display_name')
        except Exception as e:
            logger.error(f"Nominatim error: {e}")
            return None

class OpenCageProvider(GeocodingProvider):
    def __init__(self):
        self.api_key = settings.OPENCAGE_API_KEY
        self.base_url = "https://api.opencagedata.com/geocode/v1/json"

    def get_address(self, lat, lon):
        if not self.api_key:
            logger.warning("OpenCage API Key not set")
            return None
            
        try:
            params = {
                'q': f"{lat}+{lon}",
                'key': self.api_key,
                'language': 'fa'
            }
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data['results']:
                return data['results'][0]['formatted']
            return None
        except Exception as e:
            logger.error(f"OpenCage error: {e}")
            return None

class ReverseGeocodingService:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ReverseGeocodingService, cls).__new__(cls)
                cls._instance.nominatim = NominatimProvider()
                cls._instance.opencage = OpenCageProvider()
                cls._instance.providers = [cls._instance.nominatim, cls._instance.opencage]
                cls._instance.current_provider_index = 0
                cls._instance.cache = {} # Simple LRU cache equivalent
                cls._instance.cache_size = 1000
        return cls._instance

    def _get_cache_key(self, lat, lon):
        # Round to 4 decimal places (~11 meters) to hit cache for nearby points
        return f"{round(float(lat), 4)},{round(float(lon), 4)}"

    def get_address(self, lat, lon):
        # 1. Check Cache
        key = self._get_cache_key(lat, lon)
        if key in self.cache:
            # Move to end (LRU behavior)
            val = self.cache.pop(key)
            self.cache[key] = val
            logger.debug(f"Geocoding cache hit for {key}")
            return val

        # 2. Round Robin Selection
        # We try the current provider, if it fails, we try the next one (Fallback)
        # We start with the provider indicated by the counter
        start_index = self.current_provider_index
        
        # Advance the counter for NEXT time immediately (Load Balancing)
        self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
        
        for i in range(len(self.providers)):
            # Calculate actual index to try: (start + i) % len
            # i=0 -> Primary choice
            # i=1 -> Fallback choice
            idx = (start_index + i) % len(self.providers)
            provider = self.providers[idx]
            provider_name = provider.__class__.__name__
            
            logger.info(f"Attempting reverse geocoding with {provider_name} for ({lat}, {lon})")
            address = provider.get_address(lat, lon)
            
            if address:
                # Cache the result
                if len(self.cache) >= self.cache_size:
                    self.cache.pop(next(iter(self.cache))) # Remove first (oldest)
                self.cache[key] = address
                return address
            
            logger.warning(f"Provider {provider_name} failed, trying next...")

        logger.error("All reverse geocoding providers failed.")
        return None
