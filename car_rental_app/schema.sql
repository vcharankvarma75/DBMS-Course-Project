-- Car Rental Reservation & Vehicle Return Management System (SQLite, 3NF)
PRAGMA foreign_keys = ON;

CREATE TABLE branches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  state TEXT
);

CREATE TABLE customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  email TEXT,
  license_no TEXT NOT NULL UNIQUE,
  city TEXT
);

CREATE TABLE vehicles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reg_no TEXT NOT NULL UNIQUE,
  make_model TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'Sedan' CHECK (category IN ('Hatchback','Sedan','SUV','MPV','Luxury')),
  daily_rate REAL NOT NULL CHECK (daily_rate > 0),
  branch_id INTEGER NOT NULL REFERENCES branches(id),
  status TEXT NOT NULL DEFAULT 'Available' CHECK (status IN ('Available','Rented','Maintenance'))
);

CREATE TABLE reservations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
  pickup_branch_id INTEGER NOT NULL REFERENCES branches(id),
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','Confirmed','Active','Completed','Cancelled')),
  CHECK (end_date >= start_date)
);

CREATE TABLE rentals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(id),
  pickup_datetime TEXT NOT NULL,
  odometer_out INTEGER NOT NULL DEFAULT 0 CHECK (odometer_out >= 0),
  fuel_out TEXT DEFAULT 'Full' CHECK (fuel_out IN ('Full','3/4','1/2','1/4')),
  deposit REAL NOT NULL DEFAULT 0 CHECK (deposit >= 0)
);

CREATE TABLE returns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rental_id INTEGER NOT NULL UNIQUE REFERENCES rentals(id),
  return_datetime TEXT NOT NULL,
  odometer_in INTEGER NOT NULL CHECK (odometer_in >= 0),
  damage_notes TEXT DEFAULT 'None',
  late_fee REAL NOT NULL DEFAULT 0 CHECK (late_fee >= 0)
);

CREATE TABLE payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rental_id INTEGER NOT NULL REFERENCES rentals(id),
  amount REAL NOT NULL CHECK (amount >= 0),
  mode TEXT NOT NULL DEFAULT 'UPI' CHECK (mode IN ('UPI','Card','Cash','Net banking')),
  status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','SUCCESS','Failed','Refunded'))
);

CREATE TABLE activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  message TEXT NOT NULL
);

-- Indexes for fast availability / PNR style lookups
CREATE INDEX idx_res_vehicle_dates ON reservations(vehicle_id, start_date, end_date);
CREATE INDEX idx_res_customer ON reservations(customer_id);
CREATE INDEX idx_pay_rental ON payments(rental_id);

-- Trigger: block double booking and maintenance vehicles
CREATE TRIGGER trg_res_check_ins BEFORE INSERT ON reservations
WHEN NEW.status NOT IN ('Cancelled','Completed')
BEGIN
  SELECT RAISE(ABORT,'Vehicle is under maintenance')
    WHERE (SELECT status FROM vehicles WHERE id = NEW.vehicle_id) = 'Maintenance';
  SELECT RAISE(ABORT,'Vehicle is already reserved for these dates (double booking blocked)')
    WHERE EXISTS (SELECT 1 FROM reservations r WHERE r.vehicle_id = NEW.vehicle_id
      AND r.status NOT IN ('Cancelled','Completed')
      AND r.start_date <= NEW.end_date AND r.end_date >= NEW.start_date);
END;

CREATE TRIGGER trg_res_check_upd BEFORE UPDATE OF vehicle_id, start_date, end_date, status ON reservations
WHEN NEW.status NOT IN ('Cancelled','Completed')
BEGIN
  SELECT RAISE(ABORT,'Vehicle is already reserved for these dates (double booking blocked)')
    WHERE EXISTS (SELECT 1 FROM reservations r WHERE r.id <> NEW.id AND r.vehicle_id = NEW.vehicle_id
      AND r.status NOT IN ('Cancelled','Completed')
      AND r.start_date <= NEW.end_date AND r.end_date >= NEW.start_date);
END;

-- Trigger: pickup only for open reservations on an available vehicle; then sync statuses
CREATE TRIGGER trg_rental_before BEFORE INSERT ON rentals
BEGIN
  SELECT RAISE(ABORT,'Reservation must be Pending or Confirmed for pickup')
    WHERE (SELECT status FROM reservations WHERE id = NEW.reservation_id) NOT IN ('Pending','Confirmed');
  SELECT RAISE(ABORT,'Vehicle is not available for pickup')
    WHERE (SELECT v.status FROM vehicles v JOIN reservations r ON r.vehicle_id = v.id
           WHERE r.id = NEW.reservation_id) <> 'Available';
END;

CREATE TRIGGER trg_rental_after AFTER INSERT ON rentals
BEGIN
  UPDATE reservations SET status = 'Active' WHERE id = NEW.reservation_id;
  UPDATE vehicles SET status = 'Rented'
    WHERE id = (SELECT vehicle_id FROM reservations WHERE id = NEW.reservation_id);
END;

-- Trigger: a return completes the reservation and frees the vehicle
CREATE TRIGGER trg_return_after AFTER INSERT ON returns
BEGIN
  UPDATE reservations SET status = 'Completed'
    WHERE id = (SELECT reservation_id FROM rentals WHERE id = NEW.rental_id);
  UPDATE vehicles SET status = 'Available'
    WHERE id = (SELECT rs.vehicle_id FROM rentals rt JOIN reservations rs ON rs.id = rt.reservation_id
                WHERE rt.id = NEW.rental_id);
END;

-- View: revenue per branch (paid payments only)
CREATE VIEW v_revenue_by_branch AS
SELECT b.name AS branch, COALESCE(SUM(p.amount),0) AS revenue
FROM branches b
LEFT JOIN reservations rs ON rs.pickup_branch_id = b.id
LEFT JOIN rentals rt ON rt.reservation_id = rs.id
LEFT JOIN payments p ON p.rental_id = rt.id AND p.status = 'SUCCESS'
GROUP BY b.id;
