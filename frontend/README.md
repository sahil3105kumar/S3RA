# S3RA Frontend

Next.js (App Router) frontend for [S3RA](https://github.com/sahil3105kumar/S3RA). Talks to the FastAPI
backend over HTTP; has its own env, entirely separate from `backend/.env`.

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # then fill in the values, see below
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment variables

| Variable | Where to get it |
|---|---|
| `NEXT_PUBLIC_API_URL` | The backend's URL, e.g. `http://localhost:8000` locally. |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase dashboard → Project Settings → API. Same project the backend uses. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Same page — the **anon/public** key, not the service role key from `backend/.env`. Safe to expose to the browser by design. |

## Supabase Auth dashboard config

The frontend itself has no OAuth secrets — those live in Supabase, not here:

1. Supabase dashboard → Authentication → Providers → enable **Google** and **GitHub**, each with their own
   OAuth client ID/secret from the Google Cloud Console / GitHub OAuth Apps.
2. Authentication → URL Configuration → **Redirect URLs** — add:
   - `http://localhost:3000/auth/callback` (local dev)
   - `https://<your-vercel-domain>/auth/callback` (production, once deployed in Milestone 8)

No email/password provider is enabled — sign-in is Google/GitHub only, matching the backend's auth model.

## How auth works here

- `lib/supabaseClient.ts` creates a browser-only Supabase client with `persistSession: true` (session survives
  a refresh, stored in `localStorage`) and `detectSessionInUrl: true`.
- Clicking a login button calls `supabase.auth.signInWithOAuth`, which redirects to the provider and back to
  `/auth/callback`.
- Because `detectSessionInUrl` is on, the client resolves the `?code=` param on that callback page itself —
  there's no server-side token exchange route in this app. `/auth/callback` just waits for
  `onAuthStateChange` to fire and then bounces back to `/`.
- `hooks/useSession.ts` exposes the live session to the rest of the app.

## How the backend calls work

- `POST /chat` — `lib/api.ts#sendChatMessage` attaches `Authorization: Bearer <token>` only when a session
  exists; logged-out users still get answers (web search only, per the backend).
- `POST /upload` — `lib/api.ts#uploadDocument` always attaches the token; the upload UI only calls this once
  a session exists (see `components/UploadPanel.tsx`), matching the backend, which hard-requires auth here.

## Structure

```
app/
  layout.tsx            root layout, fonts
  page.tsx               home: header + chat + upload panel
  auth/callback/page.tsx  OAuth redirect landing page
components/
  Header.tsx              brand, upload trigger, session/avatar, sign out
  LoginButtons.tsx         Google/GitHub buttons only
  ChatWindow.tsx           message list + send logic
  ChatMessageBubble.tsx    one message, incl. "agent is thinking…" state
  ChatInput.tsx            textarea + send button
  ToolBadges.tsx           which tool(s) were used for an answer
  SourceList.tsx           citations (source + page) for an answer
  UploadPanel.tsx          upload modal; shows login prompt if logged out
lib/
  supabaseClient.ts        browser Supabase client
  api.ts                   fetch wrappers for /chat and /upload
  types.ts                 shared types matching the backend's response shapes
hooks/
  useSession.ts            live Supabase session as a hook
```
