import os, time, requests

BASE = os.getenv("ORDER_BASE", "http://localhost:8001").rstrip("/")

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

def test_list_orders_empty_ok():
    wait_ready(f"{BASE}/health")
    r, used = _once(f"{BASE}/orders", timeout=8)
    assert r.ok, f"List @ {used}: {r.status_code} {r.text}"
    data = r.json()
    assert isinstance(data, list)  # adjust if your API returns a different envelope
