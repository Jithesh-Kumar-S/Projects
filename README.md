# Local Service Barter Platform 

This is a Django website + a small ML matching engine (scikit-learn).
It uses SQLite (a file-based database)



## Where each project requirement lives in the code

| Requirement                 | File | 
| ML Recommendation Engine (FR-05, FR-07) | `core/recommend.py` |
| Time-credit wallet (FR-08) | `Transaction` model + `core/views.py` → `wallet()`, `_complete_exchange()` |
| Exchange workflow (FR-09) | `ExchangeRequest` model + `request_update_status()` |
| Messaging (FR-10) | `Message` model + `request_detail()` view |
| Ratings (FR-11) | `Rating` model + `rating_create()` view |
| Admin dashboard / analytics (FR-13, FR-14) | `admin_analytics()` view + Django's built-in `/admin/` |
| Search & filters (FR-04) | `listing_list()` view |


