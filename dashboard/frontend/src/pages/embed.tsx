// The dashboard as the WordPress site embeds it: no header or footer, sized to its content (see lib/embed.ts).
// Its address is /?embed=1 (next.config.ts rewrites that here), and like the main page it is rendered at build
// time, so the server HTML is already the embedded layout.

import Head from "next/head";
import Dashboard from "./index";

export default function EmbeddedDashboard() {
  return (
    <>
      <Head>
        {/* The full page (/) is the one to index */}
        <meta name="robots" content="noindex" />
      </Head>
      <Dashboard embedded />
    </>
  );
}
