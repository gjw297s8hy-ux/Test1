import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CRM Prospection IA",
  description: "CRM avec agent de prospection IA : trouver, qualifier et contacter vos prospects B2B.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
