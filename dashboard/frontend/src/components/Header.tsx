// This file defines the Header component for the WELL dashboard, including branding, navigation, and project titles.
// It displays McMaster and WELL logos, project titles, and a navigation bar.

import { useEffect, useState } from "react";
import Image from "next/image";

// Base site URL for WordPress, provided via .env.local as NEXT_PUBLIC_WP_HOME
// Falls back to production URL if not set
const WP_HOME = (process.env.NEXT_PUBLIC_WP_HOME || "https://well.mcmaster.ca").replace(/\/$/, "");

const Header = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setMobileMenuOpen(false);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Navigation items for the main nav bar
  const navItems = [
    { label: "Home", href: "/" },
    { label: "Dashboard", href: "/dashboard", active: true },
    { label: "About", href: "/about" },
    { label: "News", href: "/news" },

  ];

  return (
    <>
      {/* McMaster Header */}
      <header className="bg-white pt-[1rem] pb-[1rem] lg:pt-[1.25rem] lg:pb-[1rem] relative">
        {/* Left side: McMaster Logo (large screens only) */}
        <div className="hidden lg:flex absolute inset-y-0 left-2 sm:left-3 lg:left-12 xl:left-14 items-center lg:translate-y-5 z-10">
          <a href="https://www.mcmaster.ca" className="flex items-center">
            <Image
              src="/logos/mcmaster-logo.png"
              alt="McMaster Logo"
              width={160}
              height={80}
              sizes="(max-width: 640px) 112px, (max-width: 1024px) 128px, 160px"
              className="h-auto w-[112px] sm:w-[128px] lg:w-[160px]"
              priority
            />
          </a>
        </div>

        {/* Right side: WELL Logo (large screens only) */}
        <div className="hidden lg:flex absolute inset-y-0 right-2 sm:right-3 lg:right-12 xl:right-14 items-center lg:translate-y-3 z-10">
          <a href={WP_HOME} className="flex items-center" aria-label="WELL Home">
            <Image
              src="/logos/WELL_LogoAndTitle_TransparentBG.PNG"
              alt="Watershed Ecosystems Living Lab Logo"
              width={128}
              height={128}
              sizes="(max-width: 640px) 96px, (max-width: 1024px) 112px, 128px"
              className="h-auto w-[96px] sm:w-[112px] lg:w-[128px]"
              priority
            />
          </a>
        </div>

        <div className="container mx-auto px-4">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-center gap-2 lg:gap-5 lg:min-h-[4rem] relative">
            {/* Logos move above title before overlap (small/medium screens) */}
            <div className="lg:hidden flex w-full items-center justify-between px-2 sm:px-3 mb-1">
              <a href="https://www.mcmaster.ca" className="flex items-center">
                <Image
                  src="/logos/mcmaster-logo.png"
                  alt="McMaster Logo"
                  width={160}
                  height={80}
                  sizes="(max-width: 640px) 112px, (max-width: 1024px) 128px"
                  className="h-auto w-[112px] sm:w-[128px]"
                  priority
                />
              </a>
              <a href={WP_HOME} className="flex items-center" aria-label="WELL Home">
                <Image
                  src="/logos/WELL_LogoAndTitle_TransparentBG.PNG"
                  alt="Watershed Ecosystems Living Lab Logo"
                  width={128}
                  height={128}
                  sizes="(max-width: 640px) 96px, (max-width: 1024px) 112px"
                  className="h-auto w-[96px] sm:w-[112px]"
                  priority
                />
              </a>
            </div>

            {/* Center: Titles */}
            <div className="w-full px-4 pt-1 text-center sm:px-6 lg:px-40 lg:pt-0">
              {/* School and project titles with links */}
              <h2
                className="text-primary"
                style={{
                  fontWeight: 600,
                  fontSize: "1.36em",
                  lineHeight: 1.6,
                  letterSpacing: "1px",
                  margin: 0,
                  marginBottom: "0.06em",
                  position: "relative",
                  top: "0.35em",
                }}
              >
                <a href="https://sees.mcmaster.ca/" className="hover:text-primary transition-colors">
                  School of Earth, Environment & Society
                </a>
              </h2>
              <h1
                className="text-black"
                style={{
                  fontWeight: 600,
                  fontSize: "2.35em",
                  lineHeight: 1.2631578947,
                  letterSpacing: "1px",
                  margin: 0,
                }}
              >
                <a href={WP_HOME}>
                  Watershed and Ecosystems Living Lab
                </a>
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Bar */}
      <nav className="relative bg-primary text-primary-foreground mt-6 lg:mt-8">
        <div
          className="pointer-events-none absolute inset-x-0 -top-6 h-6"
          style={{ background: "linear-gradient(to top, rgba(0, 0, 0, 0.12), rgba(0, 0, 0, 0))" }}
          aria-hidden="true"
        />
        <div className="container mx-auto px-4">
          {/* Desktop navigation */}
          <div className="hidden md:flex items-center justify-center">
            <div className="flex w-full max-w-[80rem] h-[4rem] items-stretch">
              {/* Navigation links */}
              {navItems.map((item) => {
                const href = `${WP_HOME}${item.href}`;
                return (
                  <a
                    key={item.label}
                    href={href}
                    className={`min-w-1/2 flex-1 h-full flex items-center justify-center px-3 text-center text-base sm:text-lg transition-colors duration-200 hover:bg-white hover:text-primary sm:min-w-0 sm:px-4 ${
                      item.active
                        ? "relative after:absolute after:bottom-0 after:left-0 after:h-[3px] after:w-full after:bg-white"
                        : ""
                    }`}
                  >
                    {item.label}
                  </a>
                );
              })}
            </div>
          </div>

          {/* Mobile navigation */}
          <div className="md:hidden w-full">
            <button
              type="button"
              onClick={() => setMobileMenuOpen((open) => !open)}
              className="w-full h-[4rem] px-4 text-lg text-center text-white cursor-pointer transition-colors duration-200 hover:bg-muted hover:text-white"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-main-menu"
            >
              Main Menu
            </button>

            <div
              id="mobile-main-menu"
              className={`grid w-full overflow-hidden transition-all duration-300 ease-in-out ${
                mobileMenuOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
              }`}
            >
              <div className="min-h-0">
                {navItems.map((item) => {
                  const href = `${WP_HOME}${item.href}`;
                  return (
                    <a
                      key={item.label}
                      href={href}
                      className={`w-full h-[4rem] flex items-center justify-center px-4 text-lg text-white transition-colors duration-200 ${
                        item.active
                          ? "bg-[#2f2a26] text-white hover:bg-white hover:text-primary"
                          : "hover:bg-white hover:text-primary"
                      }`}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      {item.label}
                    </a>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </nav>
    </>
  );
};

export default Header;