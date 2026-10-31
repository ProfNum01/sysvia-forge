import { useEffect, useState } from "react";

/** Browser image elements cannot attach the operator header; use short-lived blob URLs. */
export function useProtectedImage(path: string | null | undefined, token: string) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setUrl("");
    setError("");
    if (!path || !token) return;
    const controller = new AbortController();
    let objectUrl = "";
    fetch(path, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then(async (response) => {
        if (!response.ok || !response.headers.get("content-type")?.startsWith("image/"))
          throw new Error("Evidence image is unavailable or access was denied.");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => { if (!controller.signal.aborted) setError("Evidence image is unavailable or access was denied."); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [path, token]);
  return { url, error, pending: !!path && !!token && !url && !error };
}
