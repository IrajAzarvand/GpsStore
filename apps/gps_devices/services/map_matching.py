"""
Neshan Map Matching Service

این سرویس برای فراخوانی API Map Matching نشان استفاده می‌شود.
نقاط GPS را به محتمل‌ترین مسیر روی جاده نگاشت می‌کند.
"""
import requests
import logging
import time
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MapMatchingService:
    """
    سرویس Map Matching نشان
    
    استفاده:
        service = MapMatchingService()
        matched_points = service.match_points([(35.7, 51.3), (35.71, 51.31)])
    """
    
    API_URL = "https://api.neshan.org/v3/map-matching"
    MAX_POINTS_PER_REQUEST = 1000
    MIN_POINTS_FOR_MATCHING = 2
    CACHE_TIMEOUT = 3600  # 1 hour
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    
    def __init__(self):
        """
        مقداردهی اولیه سرویس
        کلید API از متغیرهای محیطی لود می‌شود
        """
        self.api_key = settings.NESHAN_SERVICE_API_KEY
        if not self.api_key:
            logger.warning("NESHAN_SERVICE_API_KEY not found in settings")
    
    def match_points(
        self, 
        points: List[Tuple[float, float]], 
        use_cache: bool = True
    ) -> Optional[Dict]:
        """
        نگاشت نقاط GPS به مسیر روی جاده
        
        Args:
            points: لیست تاپل‌های (latitude, longitude)
            use_cache: استفاده از cache برای کاهش درخواست‌های تکراری
            
        Returns:
            دیکشنری حاوی snappedPoints و geometry یا None در صورت خطا
            
        Example:
            >>> service = MapMatchingService()
            >>> points = [(35.700393, 51.33425), (35.699708, 51.332629)]
            >>> result = service.match_points(points)
            >>> if result:
            ...     print(result['snappedPoints'])
            ...     print(result['geometry'])
        """
        if not self.api_key:
            logger.error("Cannot perform map matching: API key not configured")
            return None
        
        # بررسی تعداد نقاط
        if len(points) < self.MIN_POINTS_FOR_MATCHING:
            logger.warning(f"Need at least {self.MIN_POINTS_FOR_MATCHING} points for map matching")
            return None
        
        if len(points) > self.MAX_POINTS_PER_REQUEST:
            logger.warning(f"Too many points ({len(points)}), truncating to {self.MAX_POINTS_PER_REQUEST}")
            points = points[:self.MAX_POINTS_PER_REQUEST]
        
        # ساخت کلید cache
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(points)
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info("Returning cached map matching result")
                return cached_result
        
        # ساخت path string
        path_string = self._build_path_string(points)
        
        # فراخوانی API با retry logic
        result = self._call_api_with_retry(path_string)
        
        # ذخیره در cache
        if result and use_cache and cache_key:
            cache.set(cache_key, result, self.CACHE_TIMEOUT)
        
        return result
    
    def _build_path_string(self, points: List[Tuple[float, float]]) -> str:
        """
        ساخت رشته path برای ارسال به API
        
        Format: "lat1,lon1|lat2,lon2|lat3,lon3"
        """
        return "|".join([f"{lat},{lon}" for lat, lon in points])
    
    def _generate_cache_key(self, points: List[Tuple[float, float]]) -> str:
        """
        ساخت کلید یکتا برای cache
        """
        import hashlib
        path_string = self._build_path_string(points)
        hash_object = hashlib.md5(path_string.encode())
        return f"map_matching:{hash_object.hexdigest()}"
    
    def _call_api_with_retry(self, path_string: str) -> Optional[Dict]:
        """
        فراخوانی API با retry logic برای مدیریت خطاهای موقت
        """
        headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "path": path_string
        }
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                # بررسی وضعیت پاسخ
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Map matching successful for {len(path_string.split('|'))} points")
                    return result
                
                # مدیریت خطاها
                error_handled = self._handle_error_response(response, attempt)
                if not error_handled:
                    # خطای غیرقابل retry
                    return None
                
            except requests.exceptions.Timeout:
                logger.warning(f"Map matching API timeout (attempt {attempt}/{self.MAX_RETRIES})")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)
                    continue
                return None
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Map matching API request failed: {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)
                    continue
                return None
        
        logger.error("Map matching failed after all retry attempts")
        return None
    
    def _handle_error_response(self, response: requests.Response, attempt: int) -> bool:
        """
        مدیریت خطاهای API
        
        Returns:
            True اگر باید retry شود، False در غیر این صورت
        """
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get('message', 'Unknown error')
        except:
            error_message = response.text
        
        # خطاهای مختلف بر اساس مستندات نشان
        if status_code == 470:
            logger.error(f"CoordinateParseError (470): {error_message}")
            return False  # خطای دائمی، retry نکن
        
        elif status_code == 480:
            logger.error(f"KeyNotFound (480): Invalid API key")
            return False  # خطای دائمی
        
        elif status_code == 481:
            logger.error(f"LimitExceeded (481): API limit exceeded")
            return False  # خطای دائمی
        
        elif status_code == 482:
            logger.warning(f"RateExceeded (482): Too many requests (attempt {attempt})")
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY * attempt * 2)  # منتظر بیشتری برای rate limit
                return True  # می‌توان retry کرد
            return False
        
        elif status_code == 483:
            logger.error(f"ApiKeyTypeError (483): Wrong API key type")
            return False  # خطای دائمی
        
        elif status_code == 484:
            logger.error(f"ApiWhiteListError (484): IP not whitelisted")
            return False  # خطای دائمی
        
        elif status_code == 485:
            logger.error(f"ApiServiceListError (485): Service not enabled for this key")
            return False  # خطای دائمی
        
        elif status_code == 404:
            logger.warning(f"NotFound (404): Too many points could not be matched")
            return False  # خطای دائمی
        
        elif status_code == 500:
            logger.error(f"GenericError (500): Server error (attempt {attempt})")
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY * attempt)
                return True  # می‌توان retry کرد
            return False
        
        else:
            logger.error(f"Unexpected error ({status_code}): {error_message}")
            return False
    
    def extract_matched_coordinates(self, result: Dict) -> List[Tuple[Decimal, Decimal]]:
        """
        استخراج مختصات تصحیح شده از نتیجه API
        
        Args:
            result: نتیجه دریافتی از API
            
        Returns:
            لیست تاپل‌های (latitude, longitude) تصحیح شده
        """
        if not result or 'snappedPoints' not in result:
            return []
        
        matched_coords = []
        for point in result['snappedPoints']:
            location = point.get('location', {})
            lat = location.get('latitude')
            lon = location.get('longitude')
            
            if lat is not None and lon is not None:
                matched_coords.append((Decimal(str(lat)), Decimal(str(lon))))
        
        return matched_coords
    
    def get_geometry(self, result: Dict) -> Optional[str]:
        """
        استخراج Encoded Polyline از نتیجه API
        
        Args:
            result: نتیجه دریافتی از API
            
        Returns:
            رشته Encoded Polyline یا None
        """
        if not result:
            return None
        
        return result.get('geometry')
