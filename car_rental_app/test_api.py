import os, tempfile
os.environ["CARRENTAL_DB"]=os.path.join(tempfile.mkdtemp(),"t.db")
import app as A
c=A.app.test_client()
J=lambda r:(r.status_code,r.get_json())
print("list",J(c.get("/api/vehicles"))[0], len(c.get("/api/customers").get_json()))
# double booking blocked
print("overlap",J(c.post("/api/reservations",json=dict(customer_id=3,vehicle_id=1,pickup_branch_id=1,start_date="2026-10-20",end_date="2026-10-22",status="Pending"))))
# new valid reservation
print("new res",J(c.post("/api/reservations",json=dict(customer_id=3,vehicle_id=3,pickup_branch_id=1,start_date="2026-10-18",end_date="2026-10-21",status="Confirmed"))))
# unique
print("uniq",J(c.post("/api/customers",json=dict(name="X",phone="9876543210",license_no="Z1"))))
# FK delete blocked
print("fkdel",J(c.delete("/api/customers/1")))
# pickup + return
print("pickup",J(c.post("/api/reservations/1/pickup",json=dict(pickup_datetime="2026-10-18T10:00",odometer_out=18240,fuel_out="Full",deposit=5000))))
print("veh1",c.get("/api/vehicles").get_json()[0]["status"])
print("double pickup",J(c.post("/api/reservations/1/pickup",json={})))
print("return bad odo",J(c.post("/api/rentals/1/return",json=dict(return_datetime="2026-10-21T12:30",odometer_in=100))))
print("return",J(c.post("/api/rentals/1/return",json=dict(return_datetime="2026-10-21T12:30",odometer_in=18795,damage_notes="None"))))
print("veh1",c.get("/api/vehicles").get_json()[0]["status"], c.get("/api/reservations").get_json()[0]["status"])
print("payments",c.get("/api/payments").get_json())
d=c.get("/api/dashboard").get_json(); print("dash",{k:d[k] for k in ("available","rented","active_rentals","pending")}, d["activity"][0])
print("avail",J(c.get("/api/available?start=2026-10-18&end=2026-10-21&branch_id=1")))
print("sql ok",J(c.post("/api/sql",json=dict(sql="SELECT * FROM v_revenue_by_branch;")))[1])
print("sql bad",J(c.post("/api/sql",json=dict(sql="DELETE FROM customers"))))
print("sql ro",J(c.post("/api/sql",json=dict(sql="WITH x AS (SELECT 1) SELECT * FROM x"))))
print("index",c.get("/").status_code)
