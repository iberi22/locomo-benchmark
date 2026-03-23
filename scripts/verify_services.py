#!/usr/bin/env python3
"""
verify_services.py - Verify that all required services are running
"""

import sys
import requests
import time


def check_service(name: str, url: str, max_retries: int = 5) -> bool:
    """Check if a service is responding at the given URL."""
    print(f"Checking {name} at {url}...")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"  ✓ {name} is healthy")
                return True
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt + 1}/{max_retries} failed: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2)
    
    print(f"  ✗ {name} is not responding")
    return False


def main():
    services = {
        'Cortex': 'http://localhost:8003/health',
        'Engram': 'http://localhost:8080/health',
        'OpenClaw Engram': 'http://localhost:8081/health',
    }
    
    all_healthy = True
    for name, url in services.items():
        if not check_service(name, url):
            all_healthy = False
    
    if all_healthy:
        print("\n✓ All services are healthy")
        sys.exit(0)
    else:
        print("\n✗ Some services are not healthy")
        sys.exit(1)


if __name__ == '__main__':
    main()
