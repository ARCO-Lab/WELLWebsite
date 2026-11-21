// A module resolve hook for the test runner only, so a test can import an API route or component that uses the
// project's "@/..." path alias (tsconfig "paths": {"@/*": ["./src/*"]}). Next and the TypeScript compiler understand
// that alias; plain Node does not, so without this an `import ... from "@/lib/..."` fails with "Cannot find package".
// Registered via --import scripts/aliasHook.mjs in the "test" script. Resolve only: type stripping stays Node's job.

import { register } from "node:module";
import { pathToFileURL } from "node:url";

const srcUrl = new URL("../src/", import.meta.url).href;

register(
  "data:text/javascript," +
    encodeURIComponent(`
      const srcUrl = ${JSON.stringify(srcUrl)};
      export async function resolve(specifier, context, nextResolve) {
        if (specifier.startsWith("@/")) {
          const base = srcUrl + specifier.slice(2);
          // Next and tsc add the extension; Node needs it. Try the file as written, then as .ts / .tsx / an index.
          const candidates = /\\.[a-z]+$/.test(specifier)
            ? [base]
            : [base + ".ts", base + ".tsx", base + "/index.ts", base];
          let lastError;
          for (const candidate of candidates) {
            try {
              return await nextResolve(candidate, context);
            } catch (error) {
              lastError = error;
            }
          }
          throw lastError;
        }
        return nextResolve(specifier, context);
      }
    `),
  pathToFileURL("./").href
);
