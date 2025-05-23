import Link from "next/link";
import Image from "next/image";

export default function Header() {
  return (
    <header className="flex items-center justify-between p-4 bg-pink-900 shadow-md">
      <div className="flex items-center">
        <Image
          src="/WELL_Logo&Title_TransparentBG.PNG"
          alt="WELL Logo"
          width={150}
          height={150}
        />
        </div>
      <Link href="/">
        <button className="px-4 py-2 text-black transition bg-yellow-400 rounded hover:bg-blue-700">
          Home
        </button>
      </Link>
    </header>
  );
}
