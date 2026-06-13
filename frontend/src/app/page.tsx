"use client"

import FrameScroller from "@/components/FrameScroller"
import SectionOverlay from "@/components/SectionOverlay"
import Navbar from "@/components/Navbar"
import Footer from "@/components/Footer"
import HeroStatic from "@/components/HeroStatic"
import { motion, useScroll, useSpring } from "framer-motion"

function ScrollProgress() {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, { stiffness: 200, damping: 30 })

  return (
    <motion.div
      className="fixed top-0 left-0 right-0 z-[60] h-[1.5px] origin-left bg-gradient-to-r from-aurora via-indigo to-aurora"
      style={{ scaleX, transformOrigin: "left" }}
    />
  )
}

export default function Home() {
  return (
    <main className="relative bg-deep-black">
      <ScrollProgress />
      <Navbar />
      <HeroStatic />
      <FrameScroller />
      <SectionOverlay />
      <Footer />
    </main>
  )
}
