import { useState, type CSSProperties } from "react";
import { API_URL } from "../api/client";
import { resolveImageUrl } from "../api/imageUrls";

type DressImageProps = {
  src?: string | null;
  alt: string;
  className?: string;
  placeholderClassName?: string;
  style?: CSSProperties;
};

export default function DressImage({
  src,
  alt,
  className,
  placeholderClassName,
  style,
}: DressImageProps) {
  const resolvedSrc = resolveImageUrl(src, API_URL);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (!resolvedSrc || failedSrc === resolvedSrc) {
    return (
      <div
        className={placeholderClassName || className || "image-placeholder"}
        style={{
          display: "grid",
          placeItems: "center",
          backgroundColor: "#f0ece8",
          color: "#777",
          ...style,
        }}
        role="img"
        aria-label={alt || "Dress image unavailable"}
      >
        No Image
      </div>
    );
  }

  return (
    <img
      src={resolvedSrc}
      alt={alt}
      className={className}
      style={style}
      onError={() => {
        console.error("Dress image failed to load:", resolvedSrc);
        setFailedSrc(resolvedSrc);
      }}
    />
  );
}
