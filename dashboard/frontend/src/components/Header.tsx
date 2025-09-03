import Image from "next/image";
import Link from "next/link";

const Header = () => {
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
                src="/logos/WELL_Logo&Title_TransparentBG.png"
                alt="Watershed Ecosystems Living Lab Logo"
                width={128}
                height={128}
                className="w-36 h-36 object-contain"
                priority
              />
            </div>

            {/* Center: Titles */}
            <div className="text-center w-full">
              <h2 className="text-sm text-primary">
                <a href="https://sees.mcmaster.ca/" className="hover:text-primary transition-colors">
                  School of Earth, Environment & Society
                </a>
              </h2>
              <h1 className="text-2xl font-bold text-black">
                <Link href="localhost" className="hover:text-primary transition-colors">
                  Watershed Ecosystems Living Lab
                </Link>
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
              {navItems.map((item) => (
                <a
                  key={item.label}
                  href={`http://localhost${item.href}`}
                  className={`flex-1 text-center py-3 px-4 transition-colors duration-200 hover:bg-white hover:text-primary ${
                    item.active ? "font-bold" : ""
                  }`}
                >
                  {item.label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </nav>
    </>
  );
};

export default Header;