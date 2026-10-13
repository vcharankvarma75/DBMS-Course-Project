INSERT INTO branches (name, city, state) VALUES
 ('Hyderabad Airport Hub','Hyderabad','Telangana'),
 ('Koramangala Branch','Bengaluru','Karnataka');
INSERT INTO customers (name, phone, email, license_no, city) VALUES
 ('Rahul Verma','9876543210','rahul@gmail.com','TS0920210045','Hyderabad'),
 ('Ananya Roy','9123456780','ananya@gmail.com','KA0120190872','Bengaluru'),
 ('Karthik Nair','9988776655','karthik@gmail.com','TS0720180331','Hyderabad');
INSERT INTO vehicles (reg_no, make_model, category, daily_rate, branch_id) VALUES
 ('TS09EA4521','Hyundai Creta','SUV',2500,1),
 ('KA01MJ7788','Maruti Swift','Hatchback',1200,2),
 ('TS07FK1190','Toyota Innova','MPV',3000,1);
INSERT INTO reservations (customer_id, vehicle_id, pickup_branch_id, start_date, end_date, status) VALUES
 (1,1,1,'2026-10-18','2026-10-21','Confirmed'),
 (2,2,2,'2026-10-19','2026-10-20','Pending');
INSERT INTO activity_log (message) VALUES ('Database created and sample data loaded');
