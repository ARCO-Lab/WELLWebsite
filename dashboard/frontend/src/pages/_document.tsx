// This file customizes the HTML document Next.js renders around every page.
// It sets the page language (lang="en", for screen readers and translation) and the body's global classes.

import { Html, Head, Main, NextScript } from "next/document";

// Runs before the page is first painted: inside a frame, marks <html> with "in-frame" so globals.css hides the
// header and footer from the start. The WordPress site embeds /?embed=1, which has neither anyway (lib/embed.ts);
// this covers any other framing. <html> is outside what React hydrates, so the class causes no mismatch.
const FRAME_CHECK = `try{if(window.self!==window.top)document.documentElement.classList.add("in-frame")}catch(e){document.documentElement.classList.add("in-frame")}`;

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <script dangerouslySetInnerHTML={{ __html: FRAME_CHECK }} />
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
