import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SocialPilot AI — Social media, with a human in control.",
  description: "Plan, create, review, schedule and publish social content with AI assistance and human approval.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
