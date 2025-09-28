import time, requests, os

BASE = os.getenv("PRODUCT_BASE", "http://localhost:8000")

def wait(url, tries=60, sleep=2):
    for _ in range(tries):
        try:
            r = requests.get(url, timeout=2)
            if r.ok:
                return
        except Exception:
            pass
        time.sleep(sleep)
    raise RuntimeError(f"Service not ready: {url}")

def test_health():
    wait(f"{BASE}/health")
    r = requests.get(f"{BASE}/health", timeout=3)
    assert r.ok

def test_create_and_list_product():
    wait(f"{BASE}/health")
    payload = {"name": "HD Widget", "price": 12.34}
    r = requests.post(f"{BASE}/products", json=payload, timeout=5)
    assert r.status_code in (200, 201)

    r = requests.get(f"{BASE}/products", timeout=5)
    assert r.ok
    data = r.json()
    assert any(p.get("name") == "HD Widget" for p in (data if isinstance(data, list) else []))
