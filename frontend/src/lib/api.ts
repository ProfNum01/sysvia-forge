let operatorToken = "";
export function setApiOperatorToken(token: string) {
  operatorToken = token;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(options.headers);
    if (operatorToken && !headers.has("Authorization"))
      headers.set("Authorization", `Bearer ${operatorToken}`);
    response = await fetch(`/api${path}`, { ...options, headers });
  } catch {
    throw new Error(
      "The local API is unreachable. Start the ProofSight backend on port 8000 and retry.",
    );
  }
  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : null;
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : typeof data?.message === "string"
          ? data.message
          : `API request failed (${response.status}). Check the local backend and retry.`,
    );
  }
  if (!contentType.includes("application/json"))
    throw new Error(
      "The backend returned an unexpected response. Check that the API is running on port 8000.",
    );
  return data as T;
}
export function formatTime(value?: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}
export function label(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
