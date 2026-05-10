from cachetools import TTLCache

# 5분(300초) TTL 캐시
sewer_cache = TTLCache(maxsize=100, ttl=300)
