import type { ChatResponse, UploadResponse } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error(
    "Missing NEXT_PUBLIC_API_URL. Copy .env.local.example to .env.local and point it at the backend " +
      "(e.g. http://localhost:8000 for local dev)."
  );
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // response wasn't JSON -- fall through to the generic message below
  }
  return `Request failed with status ${res.status}`;
}

/**
 * POST /chat. Auth is optional on the backend: the Authorization header is
 * only attached when an access token is passed in, so a logged-out caller
 * gets web-search-only answers exactly as the backend expects.
 */
export async function sendChatMessage(message: string, accessToken?: string | null): Promise<ChatResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message }),
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }

  return res.json();
}

/**
 * POST /upload. Login is required by the backend (require_user_id raises
 * 401 without a token), so the JWT is always attached here -- callers of
 * this function should already have gated the UI behind a session.
 */
export async function uploadDocument(file: File, accessToken: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: formData,
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }

  return res.json();
}
