// This file is the custom App component for Next.js, used to initialize pages and inject global styles/fonts.
// It wraps all pages and sets up the global font and CSS.

import "@/styles/globals.css";
import type { AppProps } from "next/app";
import Head from "next/head";
import VisitorCount from "@/components/VisitorCount";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        {/* Load Poppins font for consistent typography */}
        <link href="https://fonts.googleapis.com/css?family=Poppins:400,600,700&display=swap" rel="stylesheet" />
      </Head>
      <Component {...pageProps} />
      {/* Page-view counting (GoatCounter, no cookies); on welldash.mcmaster.ca only */}
      <VisitorCount />
    </>
  );
}
