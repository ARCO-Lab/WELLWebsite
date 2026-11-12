// This file customizes the HTML document Next.js renders around every page.
// It sets the page language (lang="en", for screen readers and translation) and the body's global classes.

import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="en">
      <Head />
      <body className="antialiased">
        {/* Main app content */}
        <Main />
        {/* Next.js scripts */}
        <NextScript />
      </body>
    </Html>
  );
}
