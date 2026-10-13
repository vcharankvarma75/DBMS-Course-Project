# Car Rental Reservation & Vehicle Return Management System
Full-stack DBMS project: **SQLite database + Flask REST API + web frontend**.

## Run it
```bash
cd car_rental_app
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. The database file `carrental.db` is created from `schema.sql` + `seed.sql`
on first run (delete it to reset). Run `python test_api.py` for a quick end-to-end check.

## Structure
| File | Purpose |
|---|---|
| `schema.sql` | Tables (3NF), PK/FK/UNIQUE/CHECK constraints, indexes, triggers, view |
| `seed.sql` | Sample data from the presentation |
| `app.py` | Flask API: CRUD, pickup, return (transaction), dashboard, availability, read-only SQL console |
| `static/index.html` | Frontend (updates from the API after every change) |

## DBMS concepts demonstrated
- **Integrity:** PRIMARY/FOREIGN KEY, UNIQUE (reg_no, phone, licence), CHECK (dates, rates, amounts), NOT NULL
- **Triggers:** block double bookings and maintenance cars; pickup marks vehicle Rented; return marks it Available and the reservation Completed
- **Transactions (ACID):** return + payment are written in one transaction; any error rolls back
- **View:** `v_revenue_by_branch`; **Indexes** on reservations and payments
- **SQL Console tab:** run SELECT queries live (read-only)

## API (JSON)
`GET/POST /api/<table>` · `PUT/DELETE /api/<table>/<id>` · `POST /api/reservations/<id>/pickup` ·
`POST /api/rentals/<id>/return` · `GET /api/dashboard` · `GET /api/available?start&end&branch_id` · `POST /api/sql`
Tables: branches, customers, vehicles, reservations, rentals, returns, payments.
