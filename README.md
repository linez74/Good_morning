# Little Mornings ❤️

A romantic, password-gated morning dashboard for one person. The frontend is hosted on GitHub Pages; the FastAPI backend handles the password, Google OAuth, encrypted token storage, and Google Health API requests.

## Important Google Health notes

- The old Fitbit Web API was turned off on **November 2, 2026**. This project uses the new **Google Health API**.
- The person connecting must first sign in to the Google Health mobile app and link their Google account there.
- Google Health API scopes are restricted and require Google's privacy/security review. A private one-person gift still needs to comply with Google's developer terms and scope requirements. API access may not be available until Google approves the app.
- In Google's OAuth consent screen, add the account that will connect as a test user while the app is in Testing. Test-mode refresh tokens expire after 7 days. This is fine for a short test, but not reliable for an always-on gift.
- The project starts in demo mode. The frontend works with sample readings before credentials are configured.

## Architecture

- `frontend/`: static website deployed to GitHub Pages.
- `backend/`: FastAPI app deployed separately (Render is preconfigured).
- OAuth tokens are encrypted at rest with Fernet and never sent to the browser.
- The frontend keeps its short-lived dashboard session in `sessionStorage`.

## 1. Create the GitHub repository

1. Create a new **private** GitHub repository.
2. Upload the contents of this project (keep the `.github` folder).
3. Go to **Settings → Pages → Build and deployment** and select **GitHub Actions**.
4. Push to the `main` branch. The workflow deploys `frontend/`.
5. Copy the Pages URL, e.g. `https://YOUR-USERNAME.github.io/YOUR-REPO/`.

A private repository does not make the published GitHub Pages site private. The website itself is public to anyone with the URL; the backend password gate protects the dashboard. Do not put secrets or health data in the frontend or repository.

## 2. Deploy the backend

1. Sign in to Render and choose **New → Blueprint**.
2. Connect this GitHub repository and apply `render.yaml`.
3. In the new service's Environment settings, set:
   - `APP_PASSWORD`: the password you want to share with him.
   - `SESSION_SECRET`: a long random secret (Render can generate one).
   - `FERNET_KEY`: generate one locally with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   - `FRONTEND_URL`: your exact GitHub Pages URL, including the trailing slash.
   - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: from Google Cloud.
   - `GOOGLE_REDIRECT_URI`: `https://YOUR-BACKEND.onrender.com/auth/google/callback`
   - `APP_TIMEZONE`: `Asia/Beirut` (or his timezone).
4. Deploy and open `https://YOUR-BACKEND.onrender.com/`. It should show `{"service":"Little Mornings API","status":"ok"}`.

## 3. Configure Google Health API

1. Create a Google Cloud project.
2. Enable **Google Health API**.
3. Configure the OAuth consent screen. Use External and add the Google account that will connect as a Test User.
4. Create an OAuth Client ID of type **Web application**.
5. Add the backend callback URL above under **Authorized redirect URIs**. Add `https://www.google.com` too if Google's setup wizard explicitly asks for it.
6. Add these read-only scopes under Data Access:
   - `https://www.googleapis.com/auth/googlehealth.sleep.readonly`
   - `https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly`
   - `https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly`
7. Copy the client ID and client secret into Render environment variables.
8. Save/redeploy the backend.
9. The account connecting must have Google Health set up and linked in the Google Health mobile app first.

Google's official docs:
- https://developers.google.com/health/about
- https://developers.google.com/health/setup
- https://developers.google.com/health/scopes
- https://developers.google.com/health/developer-checklist
- https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list

## 4. Connect frontend to backend

Open `frontend/app.js` and replace:

`https://YOUR-BACKEND.onrender.com`

with your actual backend URL. Commit and push. GitHub Actions will redeploy the Pages site.

## 5. Test

1. Open the GitHub Pages URL.
2. Enter the password.
3. The demo dashboard should appear.
4. Click **Connect Google Health**.
5. Approve the requested permissions in Google's consent page.
6. On success, you return to the dashboard and it requests yesterday's sleep, steps, and resting heart rate.

## Security checklist before sharing

- Use a unique password and share it separately from the URL if you want an extra layer.
- Never commit `.env`, client secrets, encryption keys, OAuth tokens, or real health data.
- Keep the Render persistent disk enabled; SQLite stores encrypted tokens there.
- Use HTTPS only.
- If the backend is on a free plan that sleeps, the first request may take a little time to wake up.
- Google OAuth app verification and Google Health API restricted-scope review may be required before the integration can be used reliably. Do not represent demo data as live health data.
- This is a personal wellness display, not a medical device. It should not diagnose or interpret medical conditions.

## Notes

This is a starter implementation. Google Health API access is restricted and Google's review requirements can prevent live access until approval. The password screen and demo dashboard can be used while you complete the Google Cloud setup.
