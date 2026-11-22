"""P3 出库全链路冒烟（临时）：订单 → 分配 → 拣货 → 复核 → 发运。"""
import json

import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=120)
tok = c.post(
    "/api/v1/auth/login", json={"username": "admin", "password": "Admin@12345"}
).json()["data"]["access_token"]
h = {"Authorization": "Bearer " + tok}


def show(label, r, key="data"):
    b = r.json()
    print(label, r.status_code, json.dumps(b.get(key), ensure_ascii=True)[:180])
    return b


before = c.get("/api/v1/wms-inventory/stocks/detail", headers=h, params={"sku_id": 2}).json()["data"]
print("0 before     ", [(i["location_id"], i["stock_status"], i["qty"]) for i in before["items"]])

order = show("1 order      ", c.post("/api/v1/wms-outbound/orders", headers=h, json={
    "owner_id": 1, "owner_doc_no": "OUT-001", "order_type": "C",
    "receiver": "张三", "receiver_address": "广州市天河区",
    "lines": [{"sku_id": 2, "qty": "10"}]}))
oid = order["data"]["id"]

show("2 dup order  ", c.post("/api/v1/wms-outbound/orders", headers=h, json={
    "owner_id": 1, "owner_doc_no": "OUT-001",
    "lines": [{"sku_id": 2, "qty": "1"}]}), key="msg")

show("3 allocate   ", c.post(f"/api/v1/wms-outbound/orders/{oid}/allocate", headers=h))

detail = c.get(f"/api/v1/wms-outbound/orders/{oid}", headers=h).json()["data"]
allocs = detail["allocations"]
print("4 alloc rows ", [(a["lot_id"], a["location_id"], a["qty"]) for a in allocs])
print("5 alloc status", detail["status"])

pick = show("6 pick       ", c.post(f"/api/v1/wms-outbound/orders/{oid}/pick", headers=h))
pid = pick["data"]["id"]
pdetail = c.get(f"/api/v1/wms-outbound/picks/{pid}", headers=h).json()["data"]
print("7 pick lines ", [(x["seq"], x["sku_id"], x["lot_id"], x["location_id"], x["qty"]) for x in pdetail["lines"]])

first = pdetail["lines"][0]
show("8 wrong loc  ", c.post(f"/api/v1/wms-outbound/pick-lines/{first['id']}/confirm",
                            headers=h, json={"location_code": "WRONG-01"}), key="msg")
show("9 right loc  ", c.post(f"/api/v1/wms-outbound/pick-lines/{first['id']}/confirm",
                            headers=h, json={"location_code": "F2-A-01"}))

for ln in pdetail["lines"][1:]:
    c.post(f"/api/v1/wms-outbound/pick-lines/{ln['id']}/confirm", headers=h, json={})
print("10 pick done ", c.get(f"/api/v1/wms-outbound/picks/{pid}", headers=h).json()["data"]["status"])

show("11 check     ", c.post(f"/api/v1/wms-outbound/orders/{oid}/check", headers=h, json={
    "weight_actual": "0.5"}))

show("12 ship      ", c.post(f"/api/v1/wms-outbound/orders/{oid}/ship", headers=h, json={
    "tracking_no": "SF1234567890"}))
show("13 reship    ", c.post(f"/api/v1/wms-outbound/orders/{oid}/ship", headers=h, json={}))

after = c.get("/api/v1/wms-inventory/stocks/detail", headers=h, params={"sku_id": 2}).json()["data"]
print("14 after     ", [(i["location_id"], i["stock_status"], i["qty"]) for i in after["items"]])
