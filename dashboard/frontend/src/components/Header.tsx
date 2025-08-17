import Link from "next/link";
import Image from "next/image";
import Head from "next/head";

export default function Header() {
  return (
    <>

      {/* This first header block replicates the top McMaster-branded header */}
      <header className="relative bg-white text-black border-b border-gray-300 px-4">
        <div className="flex items-center justify-between h-[96px]">
          {/* Left side: Logo and Titles */}
          <div className="flex items-center">
            <a href="https://www.mcmaster.ca" className="flex items-center">
              <Image
                src="/mcmaster-logo.svg" // You will need to add this logo to your /public folder
                alt="McMaster Logo"
                width={160}
                height={70}
              />
            </a>
            <div className="ml-4">
              <h2 className="text-sm text-gray-600">
                <a href="https://sees.mcmaster.ca/" className="hover:underline">
                  School of Earth, Environment & Society
                </a>
              </h2>
              <h1 className="text-2xl font-bold text-[#7A003C]">
                <Link href="/" className="hover:underline">
                  Watershed Ecosystems Living Lab
                </Link>
              </h1>
            </div>
          </div>

          {/* Right side: Search and Menu Icons (placeholders) */}
          <div className="flex items-center space-x-4">
            {/* These are placeholders. You can add functionality later if needed. */}
            <button className="p-2" aria-label="Search">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
            </button>
            <button className="p-2" aria-label="Menu">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
            </button>
          </div>
        </div>
      </header>

      {/* This second nav block replicates the site-specific navigation bar */}
      <nav className="bg-[#7A003C] text-white">
        <div className="container mx-auto px-4">
          {/* This is the hard-coded version of your wp_nav_menu */}
          <ul className="flex items-center space-x-6 h-12">
            <li><a href="/" className="hover:text-yellow-400 transition-colors">Home</a></li> {/* overwrite eslint because of proxy */}
            <li><a href="/about" className="hover:text-yellow-400 transition-colors">About</a></li>
            <li><a href="/news" className="hover:text-yellow-400 transition-colors">News</a></li>
            <li className="font-bold"><a href="/dashboard" className="hover:text-yellow-400 transition-colors">Dashboard</a></li>
          </ul>
        </div>
      </nav>
    </>
  );
}