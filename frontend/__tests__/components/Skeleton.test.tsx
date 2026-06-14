import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import Skeleton, { SkeletonCard, SkeletonGauges } from "@/components/Skeleton"

describe("Skeleton", () => {
  it("renders rect variant by default", () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild as HTMLElement
    expect(el).toHaveClass("animate-pulse")
  })

  it("renders text variant with single line", () => {
    const { container } = render(<Skeleton variant="text" />)
    const el = container.firstChild as HTMLElement
    expect(el).toHaveClass("space-y-2")
  })

  it("renders text variant with multiple lines", () => {
    const { container } = render(<Skeleton variant="text" lines={3} />)
    const el = container.firstChild as HTMLElement
    expect(el.children.length).toBe(3)
  })

  it("renders circle variant", () => {
    const { container } = render(<Skeleton variant="circle" className="w-10 h-10" />)
    const el = container.firstChild as HTMLElement
    expect(el).toHaveClass("rounded-full")
  })

  it("renders card variant", () => {
    render(<Skeleton variant="card" />)
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument()
  })

  it("accepts custom className", () => {
    const { container } = render(<Skeleton className="h-20 w-full" />)
    const el = container.firstChild as HTMLElement
    expect(el).toHaveClass("h-20", "w-full")
  })
})

describe("SkeletonCard", () => {
  it("renders default 3 skeleton cards", () => {
    const { container } = render(<SkeletonCard />)
    const cards = container.querySelectorAll(".rounded-xl")
    expect(cards.length).toBe(3)
  })

  it("renders custom count of skeleton cards", () => {
    const { container } = render(<SkeletonCard count={5} />)
    const cards = container.querySelectorAll(".rounded-xl")
    expect(cards.length).toBe(5)
  })
})

describe("SkeletonGauges", () => {
  it("renders default 4 gauge skeletons", () => {
    const { container } = render(<SkeletonGauges />)
    const gauges = container.querySelectorAll(".rounded-xl")
    expect(gauges.length).toBe(4)
  })

  it("renders custom count of gauge skeletons", () => {
    const { container } = render(<SkeletonGauges count={2} />)
    const gauges = container.querySelectorAll(".rounded-xl")
    expect(gauges.length).toBe(2)
  })
})
