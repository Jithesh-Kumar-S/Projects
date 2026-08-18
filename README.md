# Local Service Barter Platform — How to Run This on Your PC

This is a Django website + a small ML matching engine (scikit-learn).
It uses SQLite (a file-based database), so there's nothing extra to
install or configure — no MySQL server needed to get started.

Follow these steps exactly, in order.

## 0. Requirements

- Python 3.10 or newer installed on your PC.
  Check with: `python --version` (Windows) or `python3 --version` (Mac/Linux)
  If you don't have Python, download it from https://www.python.org/downloads/
  **On Windows, tick "Add Python to PATH" during install.**

## 1. Unzip the project

Unzip `barter_platform.zip` anywhere, e.g. your Desktop. You should see a
folder called `barter_platform` containing `manage.py`.

## 2. Open a terminal in that folder

- **Windows:** open the `barter_platform` folder in File Explorer, click the
  address bar, type `cmd`, press Enter.
- **Mac:** open Terminal, type `cd ` (with a space), drag the folder into
  the terminal window, press Enter.

## 3. Create a virtual environment (keeps this project's packages separate)

```
python -m venv venv
```
(Mac/Linux: use `python3` instead of `python` if needed)

Activate it:
- **Windows (cmd):** `venv\Scripts\activate`
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **Mac/Linux:** `source venv/bin/activate`

You'll know it worked because your terminal line now starts with `(venv)`.

## 4. Install the required packages

```
pip install -r requirements.txt
```

This downloads Django, pandas, numpy, and scikit-learn. Needs internet,
takes a minute or two.

## 5. Create the database tables

```
python manage.py migrate
```

This creates a file called `db.sqlite3` in the folder — that's your entire
database, no server needed.

## 6. Create an admin account (for you, as the "college demo" admin)

```
python manage.py createsuperuser
```

Follow the prompts (username, email, password). This account can log into
`/admin/` and the built-in `/analytics/` dashboard.

## 7. (Recommended) Load demo data so it's not empty

```
python manage.py seed_demo
```

This creates 4 sample users (asha, rahul, meera, vijay — all password
`demo1234`) with listings that are designed to match each other, so you
can immediately demo the ML recommendation engine.

## 8. Run the server

```
python manage.py runserver
```

Now open your browser to: **http://127.0.0.1:8000/**

Leave this terminal window open while you use the site — closing it stops
the server. Press `Ctrl+C` in the terminal to stop it manually.

---

## How to actually demo it for your project evaluation

1. Log in as `rahul` (password `demo1234`) → go to **Dashboard** → you'll
   see recommended listings from `asha` and `meera` because the ML engine
   matched Rahul's "skills needed" (spanish tutoring, guitar lessons)
   against other users' listing text.
2. Click a recommended listing → **Request This Exchange**.
3. Log out, log in as the *provider* of that listing (e.g. `asha`) →
   **My Exchanges** → **Accept** the request.
4. Either user clicks **Mark Completed** → credits automatically move from
   requester to provider (check **Wallet** on both accounts to prove it).
5. Leave a **Rating** to show the trust layer.
6. Log in as your superuser → visit `/analytics/` to show the admin
   dashboard (FR-13/14), or `/admin/` for full data management.

## Where each project requirement lives in the code

| Requirement | File |
|---|---|
| ML Recommendation Engine (FR-05, FR-07) | `core/recommend.py` |
| Time-credit wallet (FR-08) | `Transaction` model + `core/views.py` → `wallet()`, `_complete_exchange()` |
| Exchange workflow (FR-09) | `ExchangeRequest` model + `request_update_status()` |
| Messaging (FR-10) | `Message` model + `request_detail()` view |
| Ratings (FR-11) | `Rating` model + `rating_create()` view |
| Admin dashboard / analytics (FR-13, FR-14) | `admin_analytics()` view + Django's built-in `/admin/` |
| Search & filters (FR-04) | `listing_list()` view |

## Common problems

- **"python is not recognized"** → Python isn't installed or not on PATH.
  Reinstall Python and check "Add to PATH".
- **`pip install` fails / times out** → check your internet connection.
- **Port already in use** → run `python manage.py runserver 8001` and
  open `http://127.0.0.1:8001/` instead.
- **Forgot to activate venv** → you'll see "No module named django". Just
  re-run the `activate` command from step 3, then try again.

## Moving to MySQL later (optional, matches the original spec exactly)

The project doc mentions MySQL 8.x. SQLite was used here to get you running
in 5 minutes with zero setup. To switch later: install `mysqlclient`
(`pip install mysqlclient`), create a MySQL database, and change the
`DATABASES` setting in `barter_platform/settings.py` to Django's MySQL
backend with your database name/user/password. Everything else in the
code stays the same — Django's ORM doesn't care which database it talks to.
