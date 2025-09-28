import os, time, requests

BASE = os.getenv("PRODUCT_BASE", "http://localhost:8000").rstrip("/")

def _once(url, method="GET", timeout=5, **kw):
    for u in (url.rstrip("/"), url.rstrip("/") + "/"):
        try:
            r = requests.request(method, u, timeout=timeout, **kw)
            return r, u
        except Exception:
            pass
    raise RuntimeError(f"Request failed for {url}")

def wait_ready(url, tries=120, sleep=1.5):
    last = None
    for _ in range(tries):
        try:
            r, used = _once(url, timeout=2)
            if r.ok:
                return used
            last = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            last = repr(e)
        time.sleep(sleep)
    raise RuntimeError(f"Service not ready: {url} (last: {last})")

def test_health():
    used = wait_ready(f"{BASE}/health")
    r, _ = _once(used, timeout=3)
    assert r.ok, f"Health failed: {r.status_code} {r.text}"

def test_create_and_list_product():
    wait_ready(f"{BASE}/health")
    payload = {
        "name": "HD Widget",
        "description": "High Distinction widget",
        "price": 12.34,
        "stock_quantity": 7,
        "image_url": "http://example.com/hd.jpg",
    }
    r, used = _once(f"{BASE}/products", method="POST", json=payload, timeout=8)
    assert r.status_code in (200, 201), f"Create @ {used}: {r.status_code} {r.text}"

    r, used = _once(f"{BASE}/products", timeout=8)
    assert r.ok, f"List @ {used}: {r.status_code} {r.text}"
    data = r.json()
    assert isinstance(data, list)
    assert any((p or {}).get("name") == "HD Widget" for p in data)