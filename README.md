# HBS vs Juventus – Automatic Ticket Checker

Monitors sections **119, 120, 121, 122, 123** on the Eventim seat map every 3 minutes.  
When 2+ seats are found together, it adds them to your cart and sends a **push notification via NTFY** so you have ~10 minutes to buy.

---

## 📋 One-Time Setup

### 1. Create the GitHub Repository

1. Go to **https://github.com/new**
2. Repository name: `HBS_Shefa`
3. Keep it **Private**
4. Do NOT add README / .gitignore
5. Click **Create repository**

### 2. Push the Code

Open a terminal inside `C:\Users\galz\source\HBS_Shefa` and run:

```powershell
git remote add origin https://github.com/galziton-hash/HBS_Shefa.git
git branch -M main
git push -u origin main
```

*(Replace `galziton-hash` with your actual GitHub username if different)*

### 3. Set GitHub Secrets

In your new repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name      | Value                    |
|-----------------|--------------------------|
| `LOGIN_EMAIL`   | `eladb8@gmail.com`       |
| `LOGIN_PASSWORD`| `Imri1212`               |
| `NTFY_TOPIC`    | `hbs-shefa`              |

### 4. Install NTFY on Your Phone

1. Download **NTFY** from the App Store or Google Play
2. Open NTFY → tap **+** → Subscribe to topic: **`hbs-shefa`**
3. Server: `https://ntfy.sh` (default)

That's it! You'll receive a loud alert the moment seats are found.

---

## ⚙️ How It Works

```
Every 3 minutes (GitHub Actions)
  │
  ├─ 1. Login to Eventim account
  ├─ 2. Open seat map for HBS vs Juventus (Event 268)
  ├─ 3. Check sections 119–123 for green (available) areas
  ├─ 4. If section found → click → count available seats
  ├─ 5. If ≥ 2 seats → add ALL to cart
  └─ 6. Send NTFY alert with section, seat details & cart URL
```

### After You Get the Alert

1. Open the link in the NTFY notification
2. Complete checkout on the Eventim site
3. You have approximately **10 minutes** before cart expires

---

## 🔍 Debugging

- Each run uploads **screenshots** as GitHub Actions artifacts (kept 3 days)
- Go to **Actions → latest run → Artifacts** to see what the browser saw
- Screenshots: `01_login_page`, `02_login_filled`, `03_after_login`, `04_seatmap_loaded`, etc.

---

## 🛑 To Stop the Checker

Go to **Actions → HBS Ticket Checker → (three dots) → Disable workflow**
