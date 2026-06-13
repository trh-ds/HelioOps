import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "HelioOps | Space Weather Impact Intelligence",
  description:
    "Predictive Space Weather Impact Intelligence platform. Real-time GPS L1 Error tracking and HF Radio Blackout probability powered by advanced ML models.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-deep-black text-white antialiased">{children}</body>
    </html>
  )
}
