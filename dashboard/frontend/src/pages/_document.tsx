// This file customizes the HTML document Next.js renders around every page.
// It sets the page language (lang="en", for screen readers and translation) and the body's global classes.

import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        {/* The headings' Poppins weights, fetched early so the title doesn't change font after it is drawn */}
        <link rel="preload" href="/fonts/poppins-700.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/poppins-600.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </Head>
      <body className="antialiased">
        {/* Main app content */}
        <Main />
        {/* Next.js scripts */}
        <NextScript />
      </body>
    </Html>
  );
}
