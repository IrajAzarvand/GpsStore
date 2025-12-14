import requests
import logging
import time
from threading import Lock
from django.conf import settings
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


def format_address_components(details):
    """
    Formats address components according to the rule:
    Province - City/County - Road - Rest (Neighborhood, etc.)
    Filters out Country and Postal Code.
    """
    if not details:
        return None
        
    parts = []
    
    # helper to clean string
    def clean(s):
        return s.strip() if s else None

    # 1. State / Province
    state = clean(details.get('state') or details.get('province') or details.get('region'))
    if state:
        parts.append(state)
        
    # 2. City / County / District
    # Priority: City -> Town -> Village -> County -> District
    city = clean(details.get('city') or details.get('town') or details.get('village') or details.get('county') or details.get('district'))
    if city and city != state: # Avoid duplicate if city name equals state (rare but possible)
        parts.append(city)
        
    # 3. Road / Street
    road = clean(details.get('road') or details.get('street') or details.get('highway') or details.get('pedestrian') or details.get('residential'))
    if road:
        parts.append(road)

    # 4. Rest (Neighborhood, Suburb, House Number, etc.)
    # We collect specific interesting keys and append them
    rest_parts = []
    priority_keys = ['neighbourhood', 'suburb', 'city_district', 'quarter', 'hamlet', 'house_number', 'building', 'public_building']
    
    # Keys to explicitly exclude (already handled or unwanted)
    excluded_keys = {'state', 'province', 'region', 'city', 'town', 'village', 'county', 'district', 
                     'road', 'street', 'highway', 'pedestrian', 'residential',
                     'country', 'country_code', 'postcode', 'iso3166-2-lvl4', 'iso3166-2-lvl6', 'ISO3166-2-lvl4'}
                     
    # First add priority keys
    for key in priority_keys:
        val = clean(details.get(key))
        if val and val not in parts and val not in rest_parts:
            rest_parts.append(val)
            
    # Then checking for other non-excluded valid strings is safer to skip to avoid noise, 
    # as APIs return many metadata keys. Sticking to priority keys is cleaner.
    
    if rest_parts:
        parts.extend(rest_parts)

    return " - ".join(parts)

class GeocodingProvider(ABC):
    @abstractmethod
    def get_address(self, lat, lon):
        pass

class NominatimProvider(GeocodingProvider):
    def __init__(self):
        self.base_url = settings.NOMINATIM_BASE_URL
        self.last_request_time = 0
        self.lock = Lock()
        self.min_interval = 1.1

    def get_address(self, lat, lon):
        if 'nominatim.openstreetmap.org' in self.base_url:
            with self.lock:
                current_time = time.time()
                elapsed = current_time - self.last_request_time
                if elapsed < self.min_interval:
                    time.sleep(self.min_interval - elapsed)
                self.last_request_time = time.time()

        try:
            headers = {
                'User-Agent': 'GpsStore/1.0 (contact@bruna.ir)'
            }
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'accept-language': 'fa',
                'addressdetails': 1 # Request detailed components
            }
            response = requests.get(self.base_url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Use custom formatter if address details exist
            if 'address' in data:
                return format_address_components(data['address'])
            
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
                result = data['results'][0]
                # OpenCage returns 'components'
                if 'components' in result:
                    return format_address_components(result['components'])
                return result['formatted']
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
                cls._instance.cache = {}
                cls._instance.cache_size = 1000
        return cls._instance

    def _get_cache_key(self, lat, lon):
        return f"{round(float(lat), 4)},{round(float(lon), 4)}"

    def get_address(self, lat, lon):
        # 1. Check Cache
        key = self._get_cache_key(lat, lon)
        if key in self.cache:
            val = self.cache.pop(key)
            self.cache[key] = val
            logger.debug(f"Geocoding cache hit for {key}")
            return val

        # 2. Round Robin Selection
        start_index = self.current_provider_index
        self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
        
        for i in range(len(self.providers)):
            idx = (start_index + i) % len(self.providers)
            provider = self.providers[idx]
            provider_name = provider.__class__.__name__
            
            logger.info(f"Attempting reverse geocoding with {provider_name} for ({lat}, {lon})")
            address = provider.get_address(lat, lon)
            
            if address:
                if len(self.cache) >= self.cache_size:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = address
                return address
            
            logger.warning(f"Provider {provider_name} failed, trying next...")

        logger.error("All reverse geocoding providers failed.")
        return None
