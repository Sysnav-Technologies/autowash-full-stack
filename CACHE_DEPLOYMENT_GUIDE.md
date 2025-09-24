# AutoWash Cache System - cPanel Deployment Guide

## Overview
This guide provides step-by-step instructions for deploying the AutoWash cache system on cPanel hosting and maintaining it after updates.

## 🚀 Initial cPanel Cache Setup Commands

### 1. First-Time Deployment Setup
Run these commands once during initial deployment or when setting up the cache system:

```bash
# 1. Create database cache table (required for hybrid cache backend)
python manage.py createcachetable

# 2. Set up cache management (creates necessary directories)
python manage.py cache_manager --create-cache-table

# 3. Initialize static file versioning
python manage.py cache_manager --update-static-version

# 4. Warm cache with initial data
python manage.py cache_manager --warm-cache

# 5. Run health check to verify everything works
python manage.py cache_manager --health-check
```

### 2. Environment Configuration Check
Verify your cPanel environment settings:

```bash
# Check if cache system detects cPanel environment correctly
python manage.py cache_manager --stats
```

Expected output should show:
- Backend: `apps.core.hybrid_cache.HybridCacheBackend`
- Cache connectivity: ✓ OK
- Using hybrid cache (memory+database) for production

## 🔄 Commands to Run After Every Update/Deployment

### Standard Update Sequence (Run these after each deployment):

```bash
# 1. Clear all existing cache to prevent stale data
python manage.py cache_manager --clear-all

# 2. Update static file version to force browser cache refresh
python manage.py cache_manager --update-static-version

# 3. Warm cache with fresh data
python manage.py cache_manager --warm-cache

# 4. Run migrations if any (standard Django)
python manage.py migrate

# 5. Collect static files (standard Django)
python manage.py collectstatic --noinput

# 6. Health check to ensure everything is working
python manage.py cache_manager --health-check
```

### Quick Update (If only content changes, no code changes):
```bash
# For minor content updates, just refresh cache
python manage.py cache_manager --update-static-version
python manage.py cache_manager --warm-cache
```

## 🛠 Troubleshooting Commands

### When Users Report Cache Issues:
```bash
# 1. Check cache system health
python manage.py cache_manager --health-check

# 2. Clear specific tenant cache (replace 'tenant_name' with actual tenant)
python manage.py cache_manager --clear-tenant=tenant_name

# 3. Performance test to check if cache is slow
python manage.py cache_manager --test-performance
```

### When Cache Seems Corrupted:
```bash
# Nuclear option - completely rebuild cache system
python manage.py cache_manager --clear-all
python manage.py createcachetable --verbosity=2
python manage.py cache_manager --update-static-version
python manage.py cache_manager --warm-cache
```

## 📋 Cache System Features

### ✅ What This System Fixes:
1. **Browser Cache Issues**: Users no longer need to clear browser cache after updates
2. **Multi-Tenant Isolation**: Each tenant's cache is properly isolated
3. **Performance**: ~0.5ms cache operations, significantly faster than file-based cache
4. **Production Ready**: Optimized for cPanel shared hosting without Redis
5. **Automatic Fallbacks**: Graceful degradation if components fail

### ✅ Cache Backends by Environment:
- **Development (localhost)**: Redis (fast, full-featured)
- **Production (cPanel)**: Hybrid Memory + Database (no Redis required)
- **Staging/Render**: Configurable based on available services

### ✅ Cache Management Features:
- Tenant-specific cache clearing
- Automatic static file versioning
- Health monitoring and diagnostics
- Performance testing
- Cache warming for frequently accessed data

## 🚨 Critical Notes for cPanel

### Environment Detection:
The system automatically detects cPanel environment and switches to hybrid cache mode. No manual configuration needed.

### Database Requirements:
- The cache system creates a `cache_table` in your main database
- No additional database setup required
- Works with existing MySQL setup

### File Permissions:
Ensure these directories are writable:
- `/static/` (for version.txt file)
- Django's cache directories (auto-created)

### Memory Usage:
- Hybrid cache limits memory usage to 5,000 entries maximum
- Automatic cleanup prevents memory bloat
- Database fallback for overflow

## 📊 Monitoring Cache Performance

### Regular Health Checks:
```bash
# Weekly or after major updates
python manage.py cache_manager --health-check
python manage.py cache_manager --stats
```

### Performance Benchmarks:
- **Good**: SET/GET operations under 1ms each
- **Acceptable**: SET/GET operations 1-5ms each  
- **Poor**: SET/GET operations over 5ms each

If performance is poor, check:
1. Database connection speed
2. Memory limits on hosting
3. Cache table size (may need clearing)

## 🔧 Template Integration

### Using Static Versioning in Templates:
Add `?v={{ static_version }}` to your static file URLs:

```html
<!-- CSS -->
<link rel="stylesheet" href="{% load static %}{% static 'css/style.css' %}?v={{ static_version }}">

<!-- JavaScript -->
<script src="{% load static %}{% static 'js/app.js' %}?v={{ static_version }}"></script>

<!-- Images -->
<img src="{% load static %}{% static 'img/logo.png' %}?v={{ static_version }}" alt="Logo">
```

The `static_version` variable is automatically available in all templates via context processor.

## 🆘 Emergency Procedures

### If Website Becomes Slow After Update:
```bash
# Quick fix sequence
python manage.py cache_manager --clear-all
python manage.py cache_manager --update-static-version  
python manage.py cache_manager --warm-cache
```

### If Users Report Seeing Old Content:
```bash
# Force browser cache refresh
python manage.py cache_manager --update-static-version

# Clear and rebuild tenant-specific cache
python manage.py cache_manager --clear-tenant=affected_tenant_name
```

### If Cache System Completely Fails:
```bash
# Switch to database-only mode temporarily by running:
python manage.py shell
```
```python
# In Django shell:
from django.core.cache import cache
cache.clear()
# Then restart your application
```

---

## 📞 Support Information

- **Cache System Version**: 2.0 (Multi-Tenant Hybrid)
- **Compatibility**: Django 4.2+, MySQL 8.0+, cPanel hosting
- **Documentation**: This file and inline code comments
- **Health Check**: `python manage.py cache_manager --health-check`

Remember: The cache system is designed to be self-healing and gracefully handle failures. Most issues resolve themselves with the standard update sequence above.