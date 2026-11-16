// ESLint for the Next.js frontend: Next's recommended rules (Core Web Vitals and TypeScript), plus a few local
// overrides. eslint-config-next ships flat configs since Next 16, so they are imported directly; `npm run lint`
// runs `eslint .` because Next 16 no longer has `next lint`.

import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Build output, and the MapLibre worker that scripts/copy-maplibre-worker.mjs copies in from node_modules.
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "public/maplibre/**"]),
  {
    rules: {
      // Use real types (or unknown and narrow it) instead of any, so the compiler checks what the data looks like.
      "@typescript-eslint/no-explicit-any": "error",
      // Temporary rule adjustment
      "@typescript-eslint/no-unused-vars": "off",
      // New in eslint-plugin-react-hooks 7 (with eslint-config-next 16). They flag existing code that works
      // (setState at the top of an effect, refs read during render), so they warn rather than fail the lint
      // until those components are reworked on their own.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
    },
  },
]);

export default eslintConfig;
