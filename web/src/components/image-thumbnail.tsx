"use client";

import { useEffect, useMemo, useState } from "react";

import webConfig from "@/constants/common-env";
import { cn } from "@/lib/utils";

export type ImageThumbnailProps = {
  src: string;
  thumbnailSrc?: string;
  alt?: string;
  className?: string;
  imageClassName?: string;
};

export function isLocalUrl(url: string): boolean {
  if (!url) return false;
  if (url.startsWith("/")) return false;
  try {
    const parsed = new URL(url, "http://localhost");
    const hostname = parsed.hostname.toLowerCase();
    return (
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "0.0.0.0" ||
      hostname === "::1" ||
      hostname === "[::1]" ||
      /^127\.\d+\.\d+\.\d+$/.test(hostname)
    );
  } catch {
    return false;
  }
}

export function extractImagePath(src: string): { type: "images" | "thumbnails" | null; relativePath: string } {
  if (!src) return { type: null, relativePath: "" };
  const imageMarker = "/images/";
  const thumbMarker = "/image-thumbnails/";

  const imgIndex = src.indexOf(imageMarker);
  if (imgIndex >= 0) {
    return {
      type: "images",
      relativePath: src.slice(imgIndex + imageMarker.length),
    };
  }

  const thumbIndex = src.indexOf(thumbMarker);
  if (thumbIndex >= 0) {
    return {
      type: "thumbnails",
      relativePath: src.slice(thumbIndex + thumbMarker.length),
    };
  }

  return { type: null, relativePath: "" };
}

export function getDomainBase(): string {
  if (webConfig.apiUrl) {
    return webConfig.apiUrl.replace(/\/$/, "");
  }
  return "";
}

export function getDomainImageUrl(src: string): string {
  const { relativePath } = extractImagePath(src);
  if (!relativePath) return src;
  const base = getDomainBase();
  return `${base}/images/${relativePath}`;
}

export function getDomainThumbnailUrl(src: string): string {
  const { relativePath } = extractImagePath(src);
  if (!relativePath) return src;
  const base = getDomainBase();
  return `${base}/image-thumbnails/${relativePath}`;
}

export function isHttpOnHttps(url: string): boolean {
  if (!url) return false;
  if (typeof window === "undefined") return false;
  if (window.location.protocol !== "https:") return false;
  return url.startsWith("http://");
}

export function resolveImageUrl(src: string): string {
  if (!src) return "";
  if (src.startsWith("/")) return src;
  if (isLocalUrl(src) || isHttpOnHttps(src)) {
    return getDomainImageUrl(src);
  }
  return src;
}

export function getImageThumbnailUrl(src: string) {
  const { relativePath } = extractImagePath(src);
  if (!relativePath) return src;

  if (isLocalUrl(src) || isHttpOnHttps(src)) {
    return getDomainThumbnailUrl(src);
  }

  const marker = "/images/";
  const index = src.indexOf(marker);
  if (index < 0) return getDomainThumbnailUrl(src);
  return `${src.slice(0, index)}/image-thumbnails/${relativePath}`;
}

export function getImageCandidates(src: string, thumbnailSrc?: string): string[] {
  if (!src) return [];
  const candidates: string[] = [];

  const add = (url: string | undefined | null) => {
    if (url && !candidates.includes(url)) {
      candidates.push(url);
    }
  };

  const isLocal = isLocalUrl(src) || (thumbnailSrc ? isLocalUrl(thumbnailSrc) : false) || isHttpOnHttps(src);
  const domainThumb = getDomainThumbnailUrl(src);
  const domainFull = getDomainImageUrl(src);
  const origThumb = thumbnailSrc || getImageThumbnailUrl(src);

  if (isLocal) {
    add(domainThumb);
    add(domainFull);
    add(origThumb);
    add(src);
  } else {
    add(origThumb);
    add(src);
    add(domainThumb);
    add(domainFull);
  }

  return candidates;
}

export function ImageThumbnail({
  src,
  thumbnailSrc,
  alt = "",
  className,
  imageClassName,
}: ImageThumbnailProps) {
  const candidates = useMemo(() => getImageCandidates(src, thumbnailSrc), [src, thumbnailSrc]);
  const [candidateIndex, setCandidateIndex] = useState(0);

  useEffect(() => {
    setCandidateIndex(0);
  }, [candidates]);

  const currentSrc = candidates[candidateIndex] || src;

  return (
    <span className={cn("block overflow-hidden bg-stone-100", className)}>
      <img
        src={currentSrc}
        alt={alt}
        className={cn("h-full w-full object-cover", imageClassName)}
        loading="lazy"
        decoding="async"
        onError={() => {
          if (candidateIndex + 1 < candidates.length) {
            setCandidateIndex((prev) => prev + 1);
          }
        }}
      />
    </span>
  );
}
