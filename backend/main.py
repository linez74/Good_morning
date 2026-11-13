import os, json, sqlite3, secrets, hashlib, hmac
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from google_auth_oauthlib.flow import Flow

APP_PASSWORD = os.environ["APP_PASSWORD"]
SESSION_SECRET = os.environ["SESSION_SECRET"]
FERNET_KEY = os.environ["FERNET_KEY"]
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPO/")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Beirut")
DATABASE_PATH = os.getenv("DATABASE_PATH", "/var/data/morning.db")
SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
]
serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="morning-session")
fernet = Fernet(FERNET_KEY.encode())
app = FastAPI(title="Little Mornings API")

origins = [FRONTEND_URL.rstrip("/")]
extra = os.getenv("EXTRA_ALLOWED_ORIGIN", "")
if extra: origins.append(extra.rstrip("/"))
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET","POST","OPTIONS"], allow_headers=["Authorization","Content-Type"])

def db():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS secrets (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS oauth_states (state TEXT PRIMARY KEY, created_at TEXT NOT NULL)")
    return conn

def save_secret(key, value):
    encrypted = fernet.encrypt(json.dumps(value).encode()).decode()
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO secrets(key,value) VALUES(?,?)", (key, encrypted))

def read_secret(key):
    with db() as conn:
        row = conn.execute("SELECT value FROM secrets WHERE key=?", (key,)).fetchone()
    return json.loads(fernet.decrypt(row[0].encode())) if row else None

def session_from_header(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please unlock the page again.")
    try:
        return serializer.loads(authorization[7:], max_age=60*60*12)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Your session expired. Please unlock the page again.")

class PasswordBody(BaseModel):
    password: str

@app.get("/")
def root():
    return {"service":"Little Mornings API","status":"ok"}

@app.post("/auth/password")
def password_login(body: PasswordBody):
    expected = hashlib.sha256(APP_PASSWORD.encode()).digest()
    supplied = hashlib.sha256(body.password.encode()).digest()
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, "That password didn't work. Try again.")
    token = serializer.dumps({"access":"dashboard"})
    return {"session_token": token}

def oauth_flow(state=None):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
        raise HTTPException(503, "Google OAuth is not configured on the backend yet.")
    config = {
      "web": {
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri":"https://accounts.google.com/o/oauth2/auth",
        "token_uri":"https://oauth2.googleapis.com/token",
        "redirect_uris":[GOOGLE_REDIRECT_URI]
      }
    }
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=GOOGLE_REDIRECT_URI)

@app.get("/auth/google/start")
def google_start(_session=Depends(session_from_header)):
    flow = oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    with db() as conn:
        conn.execute("INSERT INTO oauth_states(state,created_at) VALUES(?,?)",
                     (state, datetime.utcnow().isoformat()))
    return {"authorization_url": authorization_url}

@app.get("/auth/google/callback")
def google_callback(state: str, code: str = "", error: str = ""):
    if error:
        return RedirectResponse(FRONTEND_URL + "?oauth=error")
    with db() as conn:
        row = conn.execute("SELECT created_at FROM oauth_states WHERE state=?", (state,)).fetchone()
        conn.execute("DELETE FROM oauth_states WHERE state=?", (state,))
    if not row or datetime.utcnow() - datetime.fromisoformat(row[0]) > timedelta(minutes=10):
        raise HTTPException(400, "OAuth state expired. Please try connecting again.")
    flow = oauth_flow(state=state)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    token_data = {
      "token": credentials.token, "refresh_token": credentials.refresh_token,
      "token_uri": credentials.token_uri, "client_id": credentials.client_id,
      "client_secret": credentials.client_secret, "scopes": credentials.scopes
    }
    save_secret("google_credentials", token_data)
    # Verify Google Health account is linked before reporting success.
    identity = requests.get("https://health.googleapis.com/v4/users/me/identity",
        headers={"Authorization":f"Bearer {credentials.token}"}, timeout=20)
    if identity.status_code >= 400:
        raise HTTPException(400, "Google account authorization worked, but Google Health is not linked or not accessible yet. Open the Google Health app, link the account, then reconnect.")
    save_secret("google_identity", identity.json())
    return RedirectResponse(FRONTEND_URL + "?oauth=success")

def access_token():
    creds = read_secret("google_credentials")
    if not creds:
        raise HTTPException(400, "Connect Google Health first.")
    # Refresh on demand. Google access tokens last about one hour.
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    c = Credentials(
      token=creds.get("token"), refresh_token=creds.get("refresh_token"),
      token_uri=creds.get("token_uri"), client_id=creds.get("client_id"),
      client_secret=creds.get("client_secret"), scopes=creds.get("scopes")
    )
    if not c.valid:
        if not c.refresh_token:
            raise HTTPException(401, "Google authorization expired. Please reconnect.")
        c.refresh(Request())
        creds["token"] = c.token
        if c.refresh_token: creds["refresh_token"] = c.refresh_token
        save_secret("google_credentials", creds)
    return c.token

def get_points(data_type, filter_expr, token, page_size=100):
    url = f"https://health.googleapis.com/v4/users/me/dataTypes/{data_type}/dataPoints"
    response = requests.get(url, params={"filter":filter_expr,"pageSize":page_size},
        headers={"Authorization":f"Bearer {token}"}, timeout=25)
    if response.status_code >= 400:
        # Keep missing optional data types graceful, but surface permission/config issues.
        if response.status_code == 403:
            return []
        raise HTTPException(response.status_code, f"Google Health data request failed for {data_type}: {response.text[:240]}")
    return response.json().get("dataPoints", [])

@app.get("/health/summary")
def health_summary(_session=Depends(session_from_header)):
    token = access_token()
    tz = ZoneInfo(APP_TIMEZONE)
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    start = yesterday.isoformat()
    end = today.isoformat()
    steps = get_points("steps",
        f'steps.interval.civil_start_time >= "{start}" AND steps.interval.civil_start_time < "{end}"',
        token, 1000)
    sleep = get_points("sleep",
        f'sleep.interval.civil_end_time >= "{start}" AND sleep.interval.civil_end_time < "{today.isoformat()}"',
        token, 25)
    rhr = get_points("daily-resting-heart-rate",
        f'dailyRestingHeartRate.date >= "{start}" AND dailyRestingHeartRate.date < "{end}"',
        token, 10)

    step_total = 0
    for point in steps:
        step_total += int((point.get("steps") or {}).get("count", 0) or 0)

    sleep_minutes = None
    if sleep:
        main_sessions = [p for p in sleep if (p.get("sleep") or {}).get("metadata", {}).get("mainSleep")]
        chosen = main_sessions or sleep
        sleep_minutes = sum(int((p.get("sleep") or {}).get("summary", {}).get("minutesAsleep", 0) or 0) for p in chosen)

    heart = None
    if rhr:
        try: heart = int(rhr[0].get("dailyRestingHeartRate", {}).get("beatsPerMinute"))
        except (TypeError, ValueError): pass

    return {"sleepMinutes":sleep_minutes, "restingHeartRate":heart,
            "steps":step_total if steps else None, "date":start,
            "source":"Google Health API", "identity":read_secret("google_identity")}

@app.post("/auth/disconnect")
def disconnect(_session=Depends(session_from_header)):
    with db() as conn:
        conn.execute("DELETE FROM secrets WHERE key IN ('google_credentials','google_identity')")
    return {"ok":True}
