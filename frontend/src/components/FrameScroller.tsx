"use client"

import { useEffect, useRef, useCallback, useState } from "react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"

gsap.registerPlugin(ScrollTrigger)

const TOTAL_FRAMES = 178
const FRAME_PATH = (i: number) => `/ezgif-frame-${String(i).padStart(3, "0")}.jpg`
const SCROLL_HEIGHT_VH = 300

export default function FrameScroller() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const framesRef = useRef<HTMLImageElement[]>([])
  const currentIndexRef = useRef(-1)
  const [ready, setReady] = useState(false)
  const [loaded, setLoaded] = useState(0)

  useEffect(() => {
    const imgs: HTMLImageElement[] = []
    let loadedCount = 0

    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image()
      img.src = FRAME_PATH(i)
      img.onload = () => {
        loadedCount++
        setLoaded(loadedCount)
        if (loadedCount === TOTAL_FRAMES) setReady(true)
      }
      img.onerror = () => {
        loadedCount++
        setLoaded(loadedCount)
        if (loadedCount === TOTAL_FRAMES) setReady(true)
      }
      imgs.push(img)
    }
    framesRef.current = imgs

    return () => {
      imgs.length = 0
    }
  }, [])

  const drawFrame = useCallback((index: number) => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext("2d", { alpha: false })
    const img = framesRef.current[index]
    if (!canvas || !ctx || !img || !img.complete || img.naturalWidth === 0) return

    if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
    }

    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  }, [])

  useEffect(() => {
    if (!ready || !containerRef.current) return

    const lastFrame = TOTAL_FRAMES - 1
    drawFrame(lastFrame)
    currentIndexRef.current = lastFrame

    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: containerRef.current,
        start: "top top",
        end: "bottom bottom",
        scrub: true,
        onUpdate: (self) => {
          const index = Math.min(
            Math.floor(self.progress * (TOTAL_FRAMES - 1)),
            TOTAL_FRAMES - 1
          )
          if (index !== currentIndexRef.current) {
            currentIndexRef.current = index
            drawFrame(index)
          }
        },
      })
    }, containerRef)

    return () => ctx.revert()
  }, [ready, drawFrame])

  return (
    <>
      <div
        ref={containerRef}
        style={{ height: `${SCROLL_HEIGHT_VH}vh`, position: "relative" }}
      >
        <div className="sticky top-0 w-full overflow-hidden" style={{ height: "100dvh", zIndex: 0 }}>
          <canvas
            ref={canvasRef}
            className="w-full h-full object-cover"
            style={{ display: ready ? "block" : "none" }}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-deep-black/30 via-transparent to-deep-black/50 pointer-events-none" />
          <div className="absolute inset-0 bg-gradient-to-r from-deep-black/15 via-transparent to-deep-black/15 pointer-events-none" />
        </div>
      </div>

      {!ready && (
        <div className="fixed inset-0 z-[100] bg-deep-black flex items-center justify-center">
          <div className="text-center">
            <div className="text-2xl font-display font-bold gradient-text mb-2">HelioOps</div>
            <div className="w-48 h-px bg-white/5 overflow-hidden rounded-full">
              <div
                className="h-full bg-aurora rounded-full transition-all duration-300"
                style={{ width: `${(loaded / TOTAL_FRAMES) * 100}%` }}
              />
            </div>
            <div className="text-xs font-mono text-white/20 mt-2">
              Loading frames... {Math.round((loaded / TOTAL_FRAMES) * 100)}%
            </div>
          </div>
        </div>
      )}
    </>
  )
}