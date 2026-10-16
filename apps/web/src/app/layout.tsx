import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Blinka Hackathon",
  description: "Next.js + FastAPI monorepo",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
