import json
import http.client
import urllib.parse

def request(method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", 8080, timeout=30)
    headers = {"Content-Type": "application/json"}
    if body is not None:
        body = json.dumps(body)
    conn.request(method, path, body, headers)
    resp = conn.getresponse()
    data = resp.read().decode()
    conn.close()
    return resp.status, data

def jsonsafe(obj):
    return json.dumps(obj).replace('<', '&lt;').replace('>', '&gt;')

def main():
    print("=== STEP 1: Generate idea ===")
    status, data = request("POST", "/api/idea", {"topic": "Vastu tips for home"})
    print(f"  POST /api/idea -> HTTP {status}")
    item = json.loads(data)
    print(f"  item: id={item['id']}, stage={item['stage']}, topic={item['topic']}")

    print("\n=== STEP 2: Approve idea (trigger Atlas) ===")
    status, data = request("POST", f"/api/action/{item['id']}", {"action": "approve_idea"})
    print(f"  POST /api/action/{item['id']} -> HTTP {status}")
    a = json.loads(data)
    print(f"  stage={a['stage']}, status={a['status']}, ideas={len(a['ideas'])}")
    print(f"  idea[0]: title={a['ideas'][0]['title']}, format={a['ideas'][0]['format']}")
    item = a

    print("\n=== STEP 3: Human selects ONE idea ===")
    selected = item["ideas"][-1]["title"]
    status, data = request("POST", f"/api/action/{item['id']}", {"action": "select_idea", "selected_idea": selected})
    print(f"  POST /api/action/{item['id']} -> HTTP {status}")
    c = json.loads(data)
    print(f"  stage={c['stage']}, format={c['format']}, status={c['status']}")
    item = c

    print("\n=== STEP 4: Approve Copy ===")
    status, data = request("POST", f"/api/action/{item['id']}", {"action": "approve_copy"})
    print(f"  POST /api/action/{item['id']} -> HTTP {status}")
    cc = json.loads(data)
    print(f"  stage={cc['stage']}, status={cc['status']}")
    print(f"  copy keys: {list(cc.keys())}")
    print(f"  copy: {json.dumps(cc.get('copy'), indent=2)[:400]}")
    item = cc

    print("\n=== STEP 5: Approve Design ===")
    status, data = request("POST", f"/api/action/{item['id']}", {"action": "approve_design"})
    print(f"  POST /api/action/{item['id']} -> HTTP {status}")
    cd = json.loads(data)
    print(f"  stage={cd['stage']}, status={cd['status']}")
    print(f"  design keys: {list(cd.keys())}")
    item = cd

    print("\n=== STEP 6: Publish ===")
    status, data = request("POST", f"/api/action/{item['id']}", {"action": "publish"})
    print(f"  POST /api/action/{item['id']} -> HTTP {status}")
    cp = json.loads(data)
    print(f"  stage={cp['stage']}, status={cp['status']}, published={cp['published']}")
    print(f"  published_at: {cp.get('published_at')}")

    print("\n=== RESULT ===")
    if cp["stage"] == "done" and cp["status"] == "published_local":
        print("Full workflow PASSED")
    else:
        print("Full workflow FAILED")
        print(json.dumps(cp, indent=2))

if __name__ == "__main__":
    main()
