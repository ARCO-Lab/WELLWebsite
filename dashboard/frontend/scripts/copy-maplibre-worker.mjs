// Copies MapLibre's web worker into public/ so the map loads it from our own site.
//
// MapLibre 6 looks for its worker next to its own module (import.meta.url), which doesn't exist once the app
// is bundled, so components/map/Map.tsx points it at /maplibre/maplibre-gl-worker.mjs instead. Runs before
// `npm run dev` and `npm run build` (the Docker build included), so the copy always matches the installed
// version. The output folder is git-ignored.
import { copyFileSync, mkdirSync } from "node:fs";

const source = new URL("../node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url);
const targetDir = new URL("../public/maplibre/", import.meta.url);

mkdirSync(targetDir, { recursive: true });
copyFileSync(source, new URL("maplibre-gl-worker.mjs", targetDir));
console.log("Copied the MapLibre worker to public/maplibre/");
