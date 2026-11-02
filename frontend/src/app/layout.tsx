import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./auth.css";
import AuthProvider from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: "Jakarta SmartTax 2026 — Sistem Informasi Pajak Daerah DKI",
  description:
    "Platform Penelusuran Data Pajak Daerah Provinsi DKI Jakarta oleh Tim AI Jakarta SmartTax 2026",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#212121",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}
