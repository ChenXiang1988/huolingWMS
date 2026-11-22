"""出库开放接口 + 退回货主 冒烟（临时）。"""
import json

import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=120)
tok = c.post(
    "/api/v1/auth/login", json={"username": "admin", "password": "Admin@12345"}
).json()["data"]["access_token"]
h = {"Authorization": "Bearer " + tok}


def show(label, r, key="data"):
    b = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    print(label, r.status_code, json.dumps(b.get(key) or b.get("msg"), ensure_ascii=True)[:150])
    return b


# 重新签一把密钥（旧的可能已不在手）
key = c.post("/api/v1/wms-master-data/apikeys", headers=h, json={
    "owner_id": 1, "name": "出库接口测试"}).json()["data"]["api_key"]
kh = {"X-API-Key": key}

# 1 货主推单
show("1 push order ", c.post("/api/v1/open/v1/orders", headers=kh, json={
    "owner_doc_no": "API-OUT-001", "receiver": "李四",
    "lines": [{"sku_id": 2, "qty": "5"}]}))

# 2 查进度
show("2 query      ", c.get("/api/v1/open/v1/orders/SO000003", headers=kh))

# 3 越权查别人的单
key2 = c.post("/api/v1/wms-master-data/apikeys", headers=h, json={
    "owner_id": 2, "name": "越权2"}).json()["data"]["api_key"]
show("3 cross read ", c.get("/api/v1/open/v1/orders/SO000003", headers={"X-API-Key": key2}))

# 4 无密钥
show("4 no key     ", c.post("/api/v1/open/v1/orders", json={
    "owner_doc_no": "X", "lines": [{"sku_id": 2, "qty": "1"}]}))

# 5 退回货主：先造一条待处置（用已有 pending）
disp = c.get("/api/v1/wms-returns/disposals", headers=h).json()["data"]
print("5 pending    ", disp["total"], [(i["id"], i["qty"], i["status"]) for i in disp["items"]])

# 造一条新的破损：走一次收货
asn = c.post("/api/v1/wms-inbound/asns", headers=h, json={
    "owner_id": 1, "owner_doc_no": "RTN-SEED-1",
    "lines": [{"sku_id": 1, "expect_qty": "20"}]}).json()["data"]
rcv = c.post(f"/api/v1/wms-inbound/asns/{asn['id']}/receipts", headers=h).json()["data"]
c.put(f"/api/v1/wms-inbound/receipts/{rcv['id']}/lines", headers=h, json={
    "lines": [{"sku_id": 1, "received_qty": "20", "damaged_qty": "4"}]})
c.post(f"/api/v1/wms-inbound/receipts/{rcv['id']}/confirm", headers=h)

d2 = c.get("/api/v1/wms-returns/disposals", headers=h).json()["data"]
target = [i for i in d2["items"] if i["qty"] == "4.0000"]
did = target[-1]["id"] if target else d2["items"][-1]["id"]
print("6 new disp   ", did)

before = c.get("/api/v1/wms-inventory/stocks", headers=h, params={"sku_id": 1}).json()["data"]
print("7 before     ", [(i["stock_status"], i["qty"]) for i in before["items"]])

show("8 return own ", c.post(f"/api/v1/wms-returns/disposals/{did}/handle", headers=h,
                             json={"method": "return_owner", "reason": "客户要求退回"}))

after = c.get("/api/v1/wms-inventory/stocks", headers=h, params={"sku_id": 1}).json()["data"]
print("9 after      ", [(i["stock_status"], i["qty"]) for i in after["items"]])

row = c.get("/api/v1/wms-returns/disposals", headers=h, params={"status": "handled"}).json()["data"]
print("10 handled   ", [(i["id"], i["method"], i["status"]) for i in row["items"]][:5])
