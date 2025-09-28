import time, requests, os

BASE = os.getenv("ORDER_BASE", "http://localhost:8001")

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

def test_list_orders_empty_ok():
    wait(f"{BASE}/health")
    r = requests.get(f"{BASE}/orders", timeout=5)
    assert r.ok
    assert isinstance(r.json(), list)  # adjust if your API returns an object
