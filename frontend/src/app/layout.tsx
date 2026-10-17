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
  description: "Agente de pagos que decide qué facturas pagar dentro de tus reglas.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={interTight.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
