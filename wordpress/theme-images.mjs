// Makes the pre-sized WebP copies in home/wp-content/themes/well/img/media/ from the originals in
// home/wp-content/uploads/. The theme's templates show these photos at a few hundred pixels, but the
// originals are camera files of up to 4032 px and 13 MB; the templates now list these copies in
// srcset so each browser downloads only the width its screen needs.
//
// Run from the repo root after changing a photo or adding one to the list below:
//   npm install --no-save sharp && node wordpress/theme-images.mjs
// then commit the files it writes. Running it again on the same originals gives the same files.

import sharp from "sharp";
import { mkdirSync } from "node:fs";
import path from "node:path";

const UPLOADS = "home/wp-content/uploads";
const OUT = "home/wp-content/themes/well/img/media";

// name: output prefix; src: original under uploads/; widths: copies to make (never above the
// original's width); square: centre-crop to a square (the About page shows these photos in a
// circle with object-fit: cover, so the crop looks the same and the copy stays small);
// quality: WebP quality (photos 78, screenshots and logos higher so text and edges stay sharp).
const IMAGES = [
  // Home page hero carousel: full width of the page.
  { name: "hero-teaching", src: "2025/09/TeachingPhoto.jpg", widths: [414, 800] },
  { name: "hero-weather", src: "2025/09/weatherpreview.png", widths: [414, 720, 1080, 1600], quality: 85 },
  { name: "hero-installation", src: "2025/09/InstallationPhoto2.jpg", widths: [414, 720, 1080, 1600, 2000] },
  // Home page dashboard card.
  { name: "dashboard-preview", src: "2025/08/dashboardPreview.png", widths: [414, 720, 1080, 1600], quality: 85 },
  // About page: 300 px circles.
  { name: "about-watershed", src: "2025/08/ancasterwatershed.jpg", widths: [300, 600], square: true },
  { name: "about-weatherstation", src: "2025/09/weatherstation.jpeg", widths: [300, 600, 900], square: true },
  { name: "about-installation", src: "2025/09/InstallationPhoto1.jpeg", widths: [300, 600, 900], square: true },
  { name: "about-research", src: "2025/09/wellresearch.png", widths: [300, 600, 900], square: true },
  // About page team portraits: already small, WebP just trims them further.
  ...["ellipapangelakis.jpg", "mikewaddington.png", "seancarey.jpg", "altafarain.png", "alemugonsamo.jpg",
    "paulincoulibaly.jpg", "chowfraser.jpg", "matthewgiamou.jpg", "karenkidd.jpg", "lukhsaankumar.jpeg"]
    .map((f) => ({ name: "team-" + f.replace(/\.\w+$/, ""), src: "2025/08/" + f, widths: [null], quality: 82 })),
  // Dashboard page: SharePoint logo, shown at most 280 px wide (the original is 3000 px).
  { name: "logo-sharepoint", src: "2025/09/sharepointlogo.png", widths: [280, 560, 840], quality: 90 },
];

mkdirSync(OUT, { recursive: true });
for (const img of IMAGES) {
  const file = path.join(UPLOADS, img.src);
  // rotate() applies the camera's EXIF orientation, as browsers do when they show the original.
  const meta = await sharp(file).rotate().toBuffer({ resolveWithObject: true }).then((r) => r.info);
  const side = Math.min(meta.width, meta.height);
  for (const w of img.widths) {
    let pipe = sharp(file).rotate();
    const full = img.square ? side : meta.width;
    const width = Math.min(w ?? full, full);
    if (img.square) pipe = pipe.resize(width, width, { fit: "cover", position: "centre" });
    else if (width < full) pipe = pipe.resize({ width });
    const out = path.join(OUT, w ? `${img.name}-${w}.webp` : `${img.name}.webp`);
    const info = await pipe.webp({ quality: img.quality ?? 78, effort: 6 }).toFile(out);
    console.log(`${out}  ${info.width}x${info.height}  ${(info.size / 1024).toFixed(1)} KiB`);
  }
}
