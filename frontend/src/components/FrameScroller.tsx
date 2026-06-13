"use client"

import { useEffect, useRef, useCallback, useState } from "react"

const TOTAL_FRAMES = 178

export default function FrameScroller() {
  const imgRef = useRef<HTMLImageElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const framesRef = useRef<HTMLImageElement[]>([])
  const rafRef = useRef<number>(0)
  const currentIndexRef = useRef(0)
  const [ready, setReady] = useState(false)
  const [loaded, setLoaded] = useState(0)
  const [currentSrc, setCurrentSrc] = useState("")

  useEffect(() => {
    const imgs: HTMLImageElement[] = []
    let loadedCount = 0

    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const idx = String(i).padStart(3, "0")
      const img = new Image()
      img.src = `/frames_for_scrolling_frontend/ezgif-frame-${idx}.jpg`
      img.onload = () => {
        loadedCount++
        setLoaded(loadedCount)
        if (loadedCount === TOTAL_FRAMES) setReady(true)
      }
      img.onerror = () => {
        loadedCount++
        if (loadedCount === TOTAL_FRAMES) setReady(true)
      }
      imgs.push(img)
    }
    framesRef.current = imgs

    return () => {
      imgs.length = 0
    }
  }, [])

  const updateFrame = useCallback(() => {
    const scrollTop = window.scrollY
    const docHeight = document.documentElement.scrollHeight - window.innerHeight
    const progress = Math.min(scrollTop / docHeight, 1)
    const index = Math.min(Math.floor(progress * (TOTAL_FRAMES - 1)), TOTAL_FRAMES - 1)

    if (index !== currentIndexRef.current && framesRef.current[index]) {
      currentIndexRef.current = index
      const idx = String(index + 1).padStart(3, "0")
      setCurrentSrc(`/frames_for_scrolling_frontend/ezgif-frame-${idx}.jpg`)
    }

    rafRef.current = requestAnimationFrame(updateFrame)
  }, [])

  useEffect(() => {
    if (!ready) return

    const idx = String(1).padStart(3, "0")
    setCurrentSrc(`/frames_for_scrolling_frontend/ezgif-frame-${idx}.jpg`)
    rafRef.current = requestAnimationFrame(updateFrame)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [ready, updateFrame])

  const totalHeight = TOTAL_FRAMES * 12

  return (
    <>
      <div style={{ height: `${totalHeight}vh` }} />
      <div
        ref={containerRef}
        className="fixed inset-0 z-0 bg-deep-black"
        style={{ pointerEvents: "none" }}
      >
        <img
          ref={imgRef}
          src={currentSrc || ""}
          alt=""
          className="w-full h-full object-cover"
          style={{
            opacity: currentSrc ? 1 : 0,
            transition: "opacity 0.08s ease",
            imageRendering: "auto" as React.CSSProperties["imageRendering"],
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-deep-black/40 via-transparent to-deep-black/60" />
        <div className="absolute inset-0 bg-gradient-to-r from-deep-black/20 via-transparent to-deep-black/20" />
      </div>
      {!ready && (
        <div className="fixed inset-0 z-[100] bg-deep-black flex items-center justify-center">
          <div className="text-center">
            <div className="text-2xl font-display font-bold gradient-text mb-2">HelioOps</div>
            <div className="w-48 h-px bg-white/5 overflow-hidden rounded-full">
              <div
                className="h-full bg-gradient-to-r from-aurora to-indigo rounded-full transition-all duration-300"
                style={{ width: `${(loaded / TOTAL_FRAMES) * 100}%` }}
              />
            </div>
            <div className="text-xs font-mono text-white/20 mt-2">Loading frames... {Math.round((loaded / TOTAL_FRAMES) * 100)}%</div>
          </div>
        </div>
      )}
    </>
  )
}
