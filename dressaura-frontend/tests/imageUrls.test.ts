import assert from "node:assert/strict";
import test from "node:test";
import { resolveImageUrl } from "../src/api/imageUrls.ts";

const apiBase = "https://dressaura-deploy.onrender.com";
const cloudinaryUrl =
  "https://res.cloudinary.com/lhfaokoc/image/upload/v1791836680/dressaura/dresses/iniz22c0fpfobmfh5ihd.jpg";

test("preserves a valid Cloudinary URL exactly", () => {
  assert.equal(resolveImageUrl(cloudinaryUrl, apiBase), cloudinaryUrl);
});

test("preserves absolute backend image URLs", () => {
  const imageUrl = `${apiBase}/uploads/dresses/example.jpeg`;
  assert.equal(resolveImageUrl(imageUrl, apiBase), imageUrl);
});

test("resolves a relative legacy path against the configured API origin", () => {
  assert.equal(
    resolveImageUrl("/uploads/dresses/example.jpeg", apiBase),
    `${apiBase}/uploads/dresses/example.jpeg`,
  );
});

test("avoids duplicate upload path segments", () => {
  assert.equal(
    resolveImageUrl("/uploads/uploads/dresses/example.jpeg", apiBase),
    `${apiBase}/uploads/dresses/example.jpeg`,
  );
  assert.equal(
    resolveImageUrl(
      `${apiBase}/uploads/uploads/dresses/example.jpeg`,
      apiBase,
    ),
    `${apiBase}/uploads/dresses/example.jpeg`,
  );
});

test("repairs a duplicated backend prefix without changing the Cloudinary URL", () => {
  assert.equal(
    resolveImageUrl(`${apiBase}${cloudinaryUrl}`, apiBase),
    cloudinaryUrl,
  );
});

test("returns no URL for missing, blank, and malformed values", () => {
  assert.equal(resolveImageUrl(null, apiBase), null);
  assert.equal(resolveImageUrl("   ", apiBase), null);
  assert.equal(resolveImageUrl("https://[invalid", apiBase), null);
  assert.equal(resolveImageUrl("javascript:alert(1)", apiBase), null);
});

test("preserves browser-local upload previews", () => {
  assert.equal(resolveImageUrl("blob:https://app.example/id", apiBase), "blob:https://app.example/id");
});
