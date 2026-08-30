import type { Metadata } from "next";
import "./globals.css";
import { AppLayout } from "@/components/layout/AppLayout";

export const metadata: Metadata = {
  title: "Continuity Guardian | AI Obligation Intelligence",
  description:
    "An AI-powered obligation and commitment tracking platform where the Obligation is the atomic unit.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen">
        <AppLayout>{children}</AppLayout>
      </body>
    </html>
  );
}
