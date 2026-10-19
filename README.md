# Event Seat Monitor

Automated availability checker for a specific sporting event.  
Monitors selected seating sections and sends a push notification the moment tickets become available.

---

## How It Works

```
Runs on a schedule (GitHub Actions)
  │
  ├─ 1. Log in to the ticketing site
  ├─ 2. Navigate to the target event page
  ├─ 3. Check configured sections for available seats
  ├─ 4. If seats found → add them all to cart
  └─ 5. Send push notification (NTFY) + email alert
```

---

## Setup

### GitHub Secrets required

Configure these in **Settings → Secrets and variables → Actions**:

| Secret name        | Description                        |
|--------------------|------------------------------------|
| `LOGIN_EMAIL`      | Ticketing site account email       |
| `LOGIN_PASSWORD`   | Ticketing site account password    |
| `NTFY_TOPIC`       | Your private NTFY topic name       |
| `EMAIL_SENDER`     | Gmail address for sending alerts   |
| `EMAIL_APP_PASSWORD` | Gmail App Password               |

### Optional variables

| Variable name  | Default               |
|----------------|-----------------------|
| `NTFY_SERVER`  | `https://ntfy.sh`     |

---

## Notifications

Uses [NTFY](https://ntfy.sh) for push notifications.  
Install the NTFY app and subscribe to your private topic to receive alerts instantly.
