// This file defines the Footer component for the WELL dashboard, displaying McMaster branding, social links, and contact info.
// It includes the university logo, navigation links, social media icons, and address details.

import Image from "next/image";

const Footer = () => {
  // Social media links and SVG icons
  const socialLinks = [
    {
      name: "Instagram",
      href: "https://www.instagram.com/mcmasteru",
      className: "instagram",
      icon: (
        <svg
          id="social-instagram"
          className="social"
          style={{ maxWidth: "20px", height: "28px", fill: "#fff" }}
          xmlns="http://www.w3.org/2000/svg"
          width="17.14"
          height="17.14"
          viewBox="0 0 17.14 17.14"
        >
          <path
            className="social"
            d="M28.57,20.23q0,2.56-.06,3.54a5.23,5.23,0,0,1-1.38,3.59,5.24,5.24,0,0,1-3.59,1.38q-1,.06-3.54.06t-3.54-.06a5.24,5.24,0,0,1-3.59-1.38,5.23,5.23,0,0,1-1.38-3.59q-.06-1-.06-3.54t.06-3.54a5.23,5.23,0,0,1,1.38-3.59,5.24,5.24,0,0,1,3.59-1.38q1-.06,3.54-.06t3.54.06a5.24,5.24,0,0,1,3.59,1.38,5.23,5.23,0,0,1,1.38,3.59Q28.57,17.67,28.57,20.23Zm-7.72-7H18l-1.08,0a8.87,8.87,0,0,0-1.15.11,4.45,4.45,0,0,0-.8.21,2.92,2.92,0,0,0-1.63,1.63,4.45,4.45,0,0,0-.21.8A8.85,8.85,0,0,0,13,17.12q0,.68,0,1.08t0,1.18c0,.52,0,.8,0,.85s0,.34,0,.85,0,.91,0,1.18,0,.63,0,1.08a8.85,8.85,0,0,0,.11,1.15,4.45,4.45,0,0,0,.21.8,2.92,2.92,0,0,0,1.63,1.63,4.52,4.52,0,0,0,.8.21,8.87,8.87,0,0,0,1.15.11l1.08,0H22l1.08,0a8.87,8.87,0,0,0,1.15-.11,4.52,4.52,0,0,0,.8-.21,2.92,2.92,0,0,0,1.63-1.63,4.45,4.45,0,0,0,.21-.8A9,9,0,0,0,27,23.34q0-.68,0-1.08t0-1.18c0-.52,0-.8,0-.85s0-.34,0-.85,0-.91,0-1.18,0-.63,0-1.08A9,9,0,0,0,26.89,16a4.45,4.45,0,0,0-.21-.8,2.92,2.92,0,0,0-1.63-1.63,4.45,4.45,0,0,0-.8-.21,8.87,8.87,0,0,0-1.15-.11l-1.08,0Zm2.26,3.92a4.42,4.42,0,0,1,0,6.23,4.42,4.42,0,0,1-6.23,0,4.42,4.42,0,0,1,0-6.23,4.42,4.42,0,0,1,6.23,0ZM22,22.25a2.86,2.86,0,1,0-4-4,2.86,2.86,0,1,0,4,4Zm3.28-7.32a1,1,0,1,1-.73-.3A1,1,0,0,1,25.3,14.93Z"
            transform="translate(-11.43 -11.66)"
          />
        </svg>
      ),
    },
    {
      name: "Twitter",
      href: "https://www.x.com/mcmasteru",
      className: "twitter twitter-x",
      icon: (
        <svg
          id="social-x"
          className="social"
          style={{ maxWidth: "20px", height: "28px", fill: "#fff" }}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 512 512"
        >
          <path d="M389.2 48h70.6L305.6 224.2 487 464H345L233.7 318.6 106.5 464H35.8L200.7 275.5 26.8 48H172.4L272.9 180.9 389.2 48zM364.4 421.8h39.1L151.1 88h-42L364.4 421.8z" />
        </svg>
      ),
    },
    {
      name: "Facebook",
      href: "https://www.facebook.com/mcmasteruniversity",
      className: "facebook",
      icon: (
        <svg
          id="social-facebook"
          className="social"
          style={{ maxWidth: "20px", height: "28px", fill: "#fff" }}
          xmlns="http://www.w3.org/2000/svg"
          width="9.64"
          height="18.57"
          viewBox="0 0 9.64 18.57"
        >
          <path
            className="185192d7-0a1f-47bf-be6a-a075f203b0c8"
            d="M25,10.36v2.95H23.24a1.64,1.64,0,0,0-1.29.4,1.84,1.84,0,0,0-.33,1.21V17h3.27l-.44,3.3H21.61V28.8H18.19V20.33H15.35V17h2.85V14.59a4.32,4.32,0,0,1,1.16-3.22,4.21,4.21,0,0,1,3.09-1.14A18.54,18.54,0,0,1,25,10.36Z"
            transform="translate(-15.35 -10.23)"
          />
        </svg>
      ),
    },
    {
      name: "YouTube",
      href: "https://www.youtube.com/mcmasterutv",
      className: "youtube",
      icon: (
        <svg
          id="social-youtube"
          className="social"
          style={{ maxWidth: "18px", height: "28px", fill: "#fff" }}
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="14.06"
          viewBox="0 0 20 14.06"
        >
          <path
            className="51d5e5b1-33b4-43d8-989b-82c83fa0ef0e"
            d="M20,13.2q1.88,0,3.62,0t2.56.11l.82,0,.19,0,.26,0,.26.05a1.5,1.5,0,0,1,.32.09l.31.15a2.17,2.17,0,0,1,.35.22,2.68,2.68,0,0,1,.32.3l.17.21a3.74,3.74,0,0,1,.32.65,4.23,4.23,0,0,1,.3,1.13q.09.71.14,1.52T30,19v2a23.52,23.52,0,0,1-.2,3.24,4.45,4.45,0,0,1-.28,1.11,2.88,2.88,0,0,1-.36.69l-.16.19a2.68,2.68,0,0,1-.32.3,1.83,1.83,0,0,1-.35.21l-.31.14a1.5,1.5,0,0,1-.32.09l-.27.05-.26,0L27,27q-2.8.21-7,.21-2.31,0-4-.07t-2.24-.08l-.55,0-.4,0a5.51,5.51,0,0,1-.61-.11,3.42,3.42,0,0,1-.57-.23,2.24,2.24,0,0,1-.63-.46L10.82,26a3.74,3.74,0,0,1-.32-.65,4.23,4.23,0,0,1-.3-1.13q-.09-.71-.14-1.52T10,21.43v-2a23.67,23.67,0,0,1,.2-3.24,4.45,4.45,0,0,1,.28-1.11,2.85,2.85,0,0,1,.36-.69l.16-.19a2.75,2.75,0,0,1,.32-.3,2.17,2.17,0,0,1,.35-.22l.31-.15a1.52,1.52,0,0,1,.32-.09l.26-.05.26,0,.19,0Q15.8,13.2,20,13.2Zm-2.06,9.62L23.34,20l-5.4-2.82Z"
            transform="translate(-10 -13.2)"
          />
        </svg>
      ),
    },
    {
      name: "LinkedIn",
      href: "https://www.linkedin.com/school/164897/",
      className: "linkedin",
      icon: (
        <svg
          id="social-linkedin"
          className="social"
          style={{ maxWidth: "16px", height: "28px", fill: "#fff" }}
          xmlns="http://www.w3.org/2000/svg"
          width="17.14"
          height="16.38"
          viewBox="0 0 17.14 16.38"
        >
          <path
            className="social"
            d="M15.56,13.79A1.76,1.76,0,0,1,15,15.15a2.1,2.1,0,0,1-1.51.55h0A2,2,0,0,1,12,15.15a1.83,1.83,0,0,1-.56-1.36A1.8,1.8,0,0,1,12,12.42a2.1,2.1,0,0,1,1.5-.54,2,2,0,0,1,1.48.54A1.86,1.86,0,0,1,15.56,13.79Zm-.23,3.42V28.26H11.64V17.2Zm13.25,4.72v6.34H24.9V22.35a3.23,3.23,0,0,0-.45-1.84A1.59,1.59,0,0,0,23,19.85a1.81,1.81,0,0,0-1.18.39,2.37,2.37,0,0,0-.71,1,2.69,2.69,0,0,0-.12.9v6.17H17.36q0-4.45,0-7.22t0-3.3V17.2H21v1.61h0a4.19,4.19,0,0,1,1.09-1.21,2.9,2.9,0,0,1,1-.49,4.43,4.43,0,0,1,1.28-.17,4,4,0,0,1,3.07,1.27A5.32,5.32,0,0,1,28.57,21.92Z"
            transform="translate(-11.43 -11.88)"
          />
        </svg>
      ),
    },
  ];

  return (
    <footer className="bg-primary text-primary-foreground mt-8">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center space-y-6">
          {/* McMaster University Logo */}
          <div className="flex justify-center">
            <a
              href="https://www.mcmaster.ca/"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Image
                src="/logos/m24-bw_left-rev.svg"
                alt="McMaster University"
                width={200}
                height={48}
                className="h-20 object-contain"
                priority
              />
            </a>
          </div>

          {/* Links */}
          <div className="flex justify-center space-x-8 text-sm">
            <a
              href="https://www.mcmaster.ca/opr/html/opr/contact_us/main/contact_us.html"
              className="hover:text-secondary transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Contact
            </a>
            <a
              href="https://www.mcmaster.ca/opr/html/footer/main/terms_of_use.html"
              className="hover:text-secondary transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Terms & Conditions
            </a>
            <a
              href="https://www.mcmaster.ca/privacy/"
              className="hover:text-secondary transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Privacy Policy
            </a>
          </div>

          {/* Social Media Links */}
          <ul id="social--links" className="flex justify-center space-x-4">
            {socialLinks.map((social) => (
              <li key={social.name} className={social.className}>
                <a
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={social.name}
                  className="p-2 hover:text-secondary transition-colors"
                >
                  {social.icon}
                </a>
              </li>
            ))}
          </ul>

          {/* Address and Contact Info */}
          <div className="space-y-2 text-sm">
            <div>
              <a
                href="https://www.google.ca/maps/place/McMaster+University/@43.260879,-79.919225,17z/data=%213m1%214b1%214m2%213m1%211s0x882c84ac44f72ac1:0x399e00ea6143011c"
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold hover:text-secondary transition-colors"
              >
                1280 Main Street West Hamilton, Ontario L8S 4L8
              </a>
            </div>
            <div>
              <a
                href="tel:+19055259140"
                className="font-semibold hover:text-secondary transition-colors"
              >
                (905) 525-9140
              </a>
            </div>
            <div className="pt-2">
              <a
                href="https://www.mcmaster.ca/"
                className="font-semibold hover:text-secondary transition-colors"
              >
                © 2025 McMaster University
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;