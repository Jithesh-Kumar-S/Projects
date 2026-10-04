# Local Service Barter Platform 

This is a Django website + a small ML matching engine (scikit-learn).
It uses SQLite (a file-based database)

## Password reset email setup

By default, password reset links are printed in the terminal for local development. To send them by email, configure SMTP environment variables before starting Django:

```powershell
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_HOST_USER = "your-smtp-username"
$env:EMAIL_HOST_PASSWORD = "your-smtp-password"
$env:DEFAULT_FROM_EMAIL = "your-verified-sender@example.com"
$env:EMAIL_USE_TLS = "true"
py manage.py runserver
```

Use the SMTP host, port, sender, and credentials provided by your email service. Keep the password private. When `EMAIL_HOST` is set, Django uses SMTP; when it is unset, reset links continue to appear in the terminal.



## Where each project requirement lives in the code

| Requirement                 | File | 
| ML Recommendation Engine (FR-05, FR-07) | `core/recommend.py` |
| Time-credit wallet (FR-08) | `Transaction` model + `core/views.py` → `wallet()`, `_complete_exchange()` |
| Exchange workflow (FR-09) | `ExchangeRequest` model + `request_update_status()` |
| Messaging (FR-10) | `Message` model + `request_detail()` view |
| Ratings (FR-11) | `Rating` model + `rating_create()` view |
| Admin dashboard / analytics (FR-13, FR-14) | `admin_analytics()` view + Django's built-in `/admin/` |
| Search & filters (FR-04) | `listing_list()` view |


