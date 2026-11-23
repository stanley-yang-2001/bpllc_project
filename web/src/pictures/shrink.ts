/** The longest side of a photo as it is sent. The server keeps 512 pixels; 640 leaves it room to do its own scaling well. */
export const SEND_SIDE = 640;

/** The browser could not open the file as a picture (not an image, a kind it cannot show such as HEIC in Chrome, or damaged). */
export class PhotoUnreadable extends Error {
  constructor() {
    super("The photo could not be read.");
  }
}

/** Makes a photo small before it is sent: drawn on white at no more than SEND_SIDE pixels on its long side and written again as a JPEG.
 * A phone photo of several MB becomes about 60 KB (the API takes 2 MB at most), and re-drawing it drops its camera and location data,
 * so those never leave the device. The server does the same again and does not trust this step. */
export async function shrinkPhoto(file: Blob, side = SEND_SIDE): Promise<Blob> {
  if (typeof createImageBitmap !== "function") return file;                 // an old browser: the server checks the size and the kind
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });      // upright, as the photo is meant to be seen
  } catch {
    throw new PhotoUnreadable();
  }
  try {
    const scale = Math.min(1, side / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new PhotoUnreadable();
    ctx.fillStyle = "#ffffff";                                                // a transparent picture gets a white background
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((done) => canvas.toBlob(done, "image/jpeg", 0.85));
    if (!blob) throw new PhotoUnreadable();
    return blob;
  } finally {
    bitmap.close();
  }
}
