// This file is the custom App component for Next.js, used to initialize pages and inject global styles/fonts.
// It wraps all pages and sets up the global CSS (which also declares the Poppins font, served from public/fonts).

import "@/styles/globals.css";
import type { AppProps } from "next/app";
import VisitorCount from "@/components/VisitorCount";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Component {...pageProps} />
      {/* Page-view counting (GoatCounter, no cookies); on welldash.mcmaster.ca only */}
      <VisitorCount />
    </>
  );
}
