// This file defines the Header component for the WELL dashboard, including branding, navigation, and project titles.
// It displays McMaster and WELL logos, project titles, and a navigation bar.

import Image from "next/image";
import Link from "next/link";

// Base site URL for WordPress, provided via .env.local as NEXT_PUBLIC_WP_HOME
// Falls back to production URL if not set
const WP_HOME = (process.env.NEXT_PUBLIC_WP_HOME || "https://well.mcmaster.ca").replace(/\/$/, "");

const Header = () => {
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
      <header className="bg-white border-b border-border">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-center h-24 relative">
            {/* Left side: Logos */}
            <div className="absolute left-0 flex items-center space-x-6">
              {/* McMaster logo and WELL logo */}
              <a href="https://www.mcmaster.ca" className="flex items-center">
                <Image
                  src="/logos/mcmaster-logo.png"
                  alt="McMaster Logo"
                  width={180}
                  height={90}
                  className="w-38 h-15 object-contain"
                  priority
                />
              </a>
              <Image
                src="/logos/WELL_LogoAndTitle_TransparentBG.PNG"
                alt="Watershed Ecosystems Living Lab Logo"
                width={128}
                height={128}
                className="w-36 h-36 object-contain"
                priority
              />
            </div>

            {/* Center: Titles */}
            <div className="text-center w-full">
              {/* School and project titles with links */}
              <h2 className="text-sm text-primary">
                <a href="https://sees.mcmaster.ca/" className="hover:text-primary transition-colors">
                  School of Earth, Environment & Society
                </a>
              </h2>
              <h1 className="text-2xl font-bold text-black">
                <a href={WP_HOME} className="hover:text-primary transition-colors">
                  Watershed Ecosystems Living Lab
                </a>
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Bar */}
      <nav className="bg-primary text-primary-foreground">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-center h-12">
            <div className="flex w-full max-w-4xl">
              {/* Navigation links */}
              {navItems.map((item) => {
                const href = `${WP_HOME}${item.href}`;
                return (
                  <a
                    key={item.label}
                    href={href}
                    className={`flex-1 text-center py-3 px-4 transition-colors duration-200 hover:bg-white hover:text-primary ${
                      item.active ? "font-bold" : ""
                    }`}
                  >
                    {item.label}
                  </a>
                );
              })}
            </div>
          </div>
        </div>
      </nav>
    </>
  );
};

export default Header;