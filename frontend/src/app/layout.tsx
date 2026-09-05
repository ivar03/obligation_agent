import type { Metadata } from "next";
import "./globals.css";
import { AppLayout } from "@/components/layout/AppLayout";

export const metadata: Metadata = {
  title: "Obligation Agent | AI Reciprocal Commitment Intelligence",
  description:
    "An AI-powered obligation and commitment tracking platform where the Obligation is the atomic unit.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-stone-50 text-stone-900 min-h-screen">
        <AppLayout>{children}</AppLayout>
      </body>
    </html>
  );
}
