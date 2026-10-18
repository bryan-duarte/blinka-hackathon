import type { Metadata } from "next";
import { Inter_Tight } from "next/font/google";
import "./globals.css";

const interTight = Inter_Tight({
  subsets: ["latin"],
  weight: ["300", "400"],
  variable: "--font-inter-tight",
});

export const metadata: Metadata = {
  title: "Blinka",
  description: "Payments agent that decides which invoices to pay within your rules.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={interTight.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
