export function validateImage(
  file: { type: string; size: number } | null,
  rights: boolean,
): string | null {
  if (!file) return "Choose an image before uploading.";
  if (!rights) return "Confirm that you have the rights to use this image.";
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type))
    return "Choose a PNG, JPEG, or WebP image.";
  if (file.size > 15 * 1024 * 1024) return "Images must be 15 MiB or smaller.";
  return null;
}
