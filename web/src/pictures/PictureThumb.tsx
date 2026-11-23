import type { Picture } from "../api/types";

const BOX = { sm: "size-9 text-xl", md: "size-16 text-4xl", lg: "size-32 text-7xl" } as const;
export type ThumbSize = keyof typeof BOX;

/** A word's picture at one of three sizes: an emoji drawn as text, or the learner's photo (the small copy for the small size, the full picture
 * otherwise). It only ever sits next to the word or its meaning, so it is hidden from screen readers rather than read out twice. */
export function PictureThumb({ picture, size = "sm", className = "" }: { picture: Picture; size?: ThumbSize; className?: string }) {
  const box = `${BOX[size]} shrink-0 overflow-hidden rounded-lg bg-slate-100 ${className}`;
  if (picture.kind === "emoji")
    return <span aria-hidden className={`${box} inline-flex items-center justify-center leading-none`}>{picture.emoji}</span>;
  return <img alt="" aria-hidden src={(size === "sm" ? picture.thumb_url : picture.url) ?? undefined} loading="lazy" decoding="async" className={`${box} object-cover`} />;
}
