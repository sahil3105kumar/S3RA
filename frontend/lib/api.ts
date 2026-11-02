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
    // response wasnt json, fall through to generic message.
  }
  return `Request failed with status ${res.status}`;
}

/**
 * post chat endpoint.
 * auth is optional, so header is added only when token exists.
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
 * post upload endpoint.
 * login is required, so jwt is always attached here.
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
