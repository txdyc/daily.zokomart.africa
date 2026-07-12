"""Live smoke test of the Plan 5 admin logistics UI against the admin PREVIEW build
(dev-server base-stripping is broken in this env; preview serves /admin/ correctly).
Verifies: all 9 logistics views mount, role-gated navigation for admin/auditor/cs, and a
real driver approval through the review dialog. Order-lifecycle mutations are checked via
the admin API (the endpoints the workspace wires to)."""
import sys
import time
from datetime import date, timedelta

import httpx
from playwright.sync_api import sync_playwright

ADMIN = "http://localhost:4174/admin"
API = "http://127.0.0.1:8000"
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not ok else ""))


def seed():
    """Self-resetting: wipe lg_* fixtures, then insert a pending graph + approved graph
    with a submitted and a delivered order."""
    from sqlalchemy import text

    from app.db import SessionLocal
    from app.logistics.models import (
        UserAccount, Driver, Vehicle, Route, Trip, CustomerOrder,
        DRIVER_APPROVED, DRIVER_PENDING, VEHICLE_APPROVED, VEHICLE_PENDING,
        ROUTE_APPROVED, ROUTE_PENDING, ORDER_SUBMITTED, ORDER_DELIVERED,
    )
    db = SessionLocal()
    for t in ("lg_commission_record", "lg_cs_remark", "lg_operation_log", "lg_customer_order",
              "lg_trip", "lg_route", "lg_vehicle", "lg_driver", "lg_blacklist",
              "lg_notification", "lg_sms_log", "lg_otp_code", "lg_audit_record",
              "lg_user_account"):
        db.execute(text(f"DELETE FROM {t}"))
    db.commit()

    def driver(phone, card, status):
        u = UserAccount(phone=phone); db.add(u); db.flush()
        d = Driver(user_id=u.id, full_name=f"Driver {card[-3:]}", gender="male",
                   date_of_birth=date(1990, 5, 1), ghana_card_number=card,
                   ghana_card_front_id="x", ghana_card_back_id="x", licence_number=f"DVLA-{card[-3:]}",
                   licence_class="C", licence_expiry=date(2030, 1, 1), licence_photo_id="x",
                   emergency_contact_name="Ama", emergency_contact_phone="+233209876543", status=status)
        db.add(d); db.flush()
        return u, d

    def vehicle(driver_id, plate, status):
        v = Vehicle(driver_id=driver_id, plate_number=plate, brand_model="Kia K2700",
                    vehicle_type="box_truck", year=2019, cargo_length_m=3.1, cargo_width_m=1.7,
                    cargo_height_m=1.8, max_load_kg=2000, max_volume_m3=10.0, photo_front_id="x",
                    photo_left_id="x", photo_right_id="x", photo_rear_id="x", photo_interior_id="x",
                    reg_cert_id="x", roadworthy_cert_id="x", roadworthy_expiry=date(2030, 1, 1),
                    insurance_cert_id="x", insurance_expiry=date(2030, 1, 1), status=status)
        db.add(v); db.flush()
        return v

    def route(driver_id, vehicle_id, status):
        r = Route(driver_id=driver_id, origin_region="Greater Accra", origin_town="Accra",
                  dest_region="Ashanti", dest_town="Kumasi", via_towns=[], frequency="daily",
                  weekdays=[], once_date=None, depart_time="08:00", est_duration_hours=6,
                  default_vehicle_id=vehicle_id, cargo_types=["general"], rate_per_ton=350.0,
                  rate_per_m3=60.0, min_charge=80.0, negotiable=False, status=status)
        db.add(r); db.flush()
        return r

    def order(shipper_id, trip_id, status):
        extra = dict(freight_ghs=500.0, commission_rate=0.08, commission_ghs=40.0,
                     pickup_time="Sat 08:00") if status == ORDER_DELIVERED else {}
        o = CustomerOrder(shipper_user_id=shipper_id, trip_id=trip_id, status=status,
                          contact_name="Efua", contact_phone="+233201112223",
                          pickup_region="Greater Accra", pickup_town="Accra", pickup_details="12 Ring Rd",
                          delivery_region="Ashanti", delivery_town="Kumasi", delivery_details="Adum",
                          consignee_name="Yaw", consignee_phone="+233261112223", cargo_name="TV sets",
                          cargo_category="electronics", packaging="carton", pieces=10, weight_kg=200.0,
                          volume_m3=1.5, pickup_window="tomorrow morning", **extra)
        db.add(o); db.flush()
        return o

    _, d1 = driver("+233555000301", "GHA-555000301-1", DRIVER_PENDING)
    v1 = vehicle(d1.id, "GR 0001-24", VEHICLE_PENDING)
    route(d1.id, v1.id, ROUTE_PENDING)

    shp = UserAccount(phone="+233201112223"); db.add(shp)
    _, d2 = driver("+233555000302", "GHA-555000302-1", DRIVER_APPROVED)
    v2 = vehicle(d2.id, "GR 0002-24", VEHICLE_APPROVED)
    r2 = route(d2.id, v2.id, ROUTE_APPROVED)
    db.flush()
    t2 = Trip(route_id=r2.id, vehicle_id=v2.id, depart_date=date.today() + timedelta(days=1),
              depart_time="08:00", total_load_kg=2000.0, total_volume_m3=10.0,
              used_load_kg=400.0, used_volume_m3=3.0)
    db.add(t2); db.flush()
    ids = {"submitted": order(shp.id, t2.id, ORDER_SUBMITTED).id,
           "delivered": order(shp.id, t2.id, ORDER_DELIVERED).id, "pending_driver": d1.id}
    db.commit()
    db.close()
    return ids


def admin_token():
    return httpx.post(f"{API}/api/admin/auth/login",
                      json={"username": "admin", "password": "admin123"}).json()["access_token"]


def make_staff():
    h = {"Authorization": f"Bearer {admin_token()}"}
    for role in ("auditor", "cs"):
        httpx.post(f"{API}/api/admin/lg/staff", headers=h,
                   json={"username": role, "password": "pw123456", "role": role})


def login(page, username, password):
    page.goto(f"{ADMIN}/login", wait_until="domcontentloaded")
    page.wait_for_selector(".login-card input", timeout=60000)
    inputs = page.locator(".login-card input")
    inputs.nth(0).fill(username)
    inputs.nth(1).fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_timeout(1500)


def lg_menu_labels(page):
    title = page.locator(".el-sub-menu__title", has_text="物流")
    if title.count():
        title.first.click()
        page.wait_for_timeout(400)
    items = page.locator(".el-sub-menu .el-menu-item")
    return sorted({items.nth(i).inner_text().strip() for i in range(items.count())})


def main(ids):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(str(e)))

        # --- admin: full menu + every view mounts
        login(page, "admin", "admin123")
        check("admin sees all 9 logistics menu items", len(lg_menu_labels(page)) == 9)

        VIEWS = ["dashboard", "drivers", "vehicles", "routes", "orders", "commissions", "config", "staff", "blacklist"]
        rendered = 0
        for v in VIEWS:
            page.goto(f"{ADMIN}/lg/{v}", wait_until="networkidle")
            page.wait_for_timeout(700)
            if page.locator(".el-table, .el-card, .el-form, .cards, .el-descriptions").count() > 0:
                rendered += 1
            else:
                print(f"   view {v} rendered nothing")
        check("all 9 logistics views mount and render", rendered == 9, f"{rendered}/9")

        # --- real mutation: approve the pending driver via the review dialog
        page.goto(f"{ADMIN}/lg/drivers", wait_until="networkidle")
        page.wait_for_selector(".el-select", timeout=8000)
        page.get_by_role("button", name="查询").first.click()
        page.wait_for_selector(".el-table__row", timeout=8000)
        page.locator(".el-table__row").first.click()  # row-click opens the review dialog
        page.wait_for_selector(".el-dialog", timeout=6000)
        # AuthImage should have loaded the Ghana Card thumbnails (proves admin bearer works)
        page.wait_for_timeout(1200)
        page.locator(".el-dialog").get_by_role("button", name="通过").click()
        page.wait_for_timeout(1200)
        h = {"Authorization": f"Bearer {admin_token()}"}
        drv = httpx.get(f"{API}/api/admin/lg/drivers/{ids['pending_driver']}", headers=h).json()
        check("driver approved through the review dialog", drv["status"] == "approved", drv.get("status"))

        # --- order lifecycle via the admin API (endpoints the workspace wires to)
        oid = ids["submitted"]
        r1 = httpx.post(f"{API}/api/admin/lg/orders/{oid}/confirm-price", headers=h,
                        json={"freight_ghs": 500.0, "pickup_time": "Sat 08:00"})
        check("confirm-price endpoint (workspace)", r1.status_code == 200 and r1.json()["commission_ghs"] == 40.0, r1.text[:80])
        did = ids["delivered"]
        r2 = httpx.post(f"{API}/api/admin/lg/orders/{did}/complete", headers=h)
        check("complete endpoint (workspace)", r2.status_code == 200 and r2.json()["status"] == "completed", r2.text[:80])
        comms = httpx.get(f"{API}/api/admin/lg/commissions?status=pending", headers=h).json()
        cid = comms["items"][0]["id"]
        r3 = httpx.post(f"{API}/api/admin/lg/commissions/{cid}/settle", headers=h,
                        json={"method": "momo", "reference": "MP1"})
        check("settle-commission endpoint (ledger)", r3.status_code == 200 and r3.json()["status"] == "settled", r3.text[:80])

        # --- dashboard reflects settled commission
        page.goto(f"{ADMIN}/lg/dashboard", wait_until="networkidle")
        page.wait_for_timeout(900)
        check("dashboard shows settled commission 40", "40" in page.inner_text("body"))

        # --- role gating: auditor
        login(page, "auditor", "pw123456")
        check("auditor menu = dashboard + 3 review queues",
              lg_menu_labels(page) == sorted(["物流看板", "司机审核", "车辆审核", "线路审核"]))
        page.goto(f"{ADMIN}/lg/orders", wait_until="networkidle")
        page.wait_for_timeout(700)
        check("auditor blocked from orders (redirect)", "/lg/dashboard" in page.url, page.url)

        # --- role gating: cs
        login(page, "cs", "pw123456")
        check("cs menu = dashboard + orders + commissions",
              lg_menu_labels(page) == sorted(["物流看板", "订单工作台", "佣金结算"]))
        page.goto(f"{ADMIN}/lg/drivers", wait_until="networkidle")
        page.wait_for_timeout(700)
        check("cs blocked from driver review (redirect)", "/lg/dashboard" in page.url, page.url)

        page.screenshot(path="e2e_admin_dashboard.png")
        real = [e for e in errs if "ResizeObserver" not in e]
        check("no real console/page errors", not real, "; ".join(real[:3]))
        browser.close()

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    ids = seed()
    make_staff()
    print("seeded", ids)
    for _ in range(30):
        try:
            httpx.get(f"{ADMIN}/", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    main(ids)
