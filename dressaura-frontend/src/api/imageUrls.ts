const HTTP_URL_PATTERN = /^https?:\/\//i;
const CLOUDINARY_HOST = "res.cloudinary.com";

export function resolveImageUrl(
  imageUrl: string | null | undefined,
  apiBaseUrl: string,
): string | null {
  if (typeof imageUrl !== "string") return null;

  let value = imageUrl.trim();
  if (!value) return null;

  const apiBase = apiBaseUrl.replace(/\/+$/, "");
  if (apiBase && value.startsWith(apiBase)) {
    const suffix = value.slice(apiBase.length);
    if (HTTP_URL_PATTERN.test(suffix) || suffix.startsWith(apiBase)) {
      value = suffix;
    }
  }

  if (HTTP_URL_PATTERN.test(value)) {
    try {
      const parsed = new URL(value);
      if (parsed.hostname.toLowerCase() === CLOUDINARY_HOST) {
        return value;
      }

      const apiOrigin = apiBase ? new URL(apiBase).origin : null;
      if (parsed.origin === apiOrigin) {
        const normalizedPath = parsed.pathname.replace(
          /^(\/uploads)(?:\/uploads)+(?=\/|$)/,
          "$1",
        );
        if (normalizedPath !== parsed.pathname) {
          parsed.pathname = normalizedPath;
          return parsed.toString();
        }
      }
      return value;
    } catch {
      return null;
    }
  }

  if (/^(?:blob|data):/i.test(value)) {
    return value;
  }
  if (/^[a-z][a-z\d+.-]*:/i.test(value)) {
    return null;
  }

  if (value.startsWith("//")) {
    try {
      return new URL(value, apiBase).toString();
    } catch {
      return null;
    }
  }

  const path = value.replace(/^(\/uploads)(?:\/uploads)+(?=\/|$)/, "$1");
  try {
    return new URL(path.replace(/^\/+/, ""), `${apiBase}/`).toString();
  } catch {
    return null;
  }
}
