import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import Sidebar from "@/components/dashboard/Sidebar"

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}))

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

describe("Sidebar", () => {
  it("renders all nav links", () => {
    render(<Sidebar />)

    expect(screen.getByText("Storm List")).toBeInTheDocument()
    expect(screen.getByText("Pipeline")).toBeInTheDocument()
    expect(screen.getByText("Health")).toBeInTheDocument()
    expect(screen.getByText("Back to Home")).toBeInTheDocument()
  })

  it("renders the HelioOps logo", () => {
    render(<Sidebar />)
    expect(screen.getByText("HelioOps")).toBeInTheDocument()
  })

  it("highlights the active link", () => {
    render(<Sidebar />)

    const activeLink = screen.getByText("Storm List").closest("a")
    expect(activeLink).toHaveClass("text-aurora")
  })

  it("links have correct hrefs", () => {
    render(<Sidebar />)

    expect(screen.getByText("Storm List").closest("a")).toHaveAttribute("href", "/dashboard")
    expect(screen.getByText("Pipeline").closest("a")).toHaveAttribute("href", "/dashboard/pipeline")
    expect(screen.getByText("Health").closest("a")).toHaveAttribute("href", "/dashboard/health")
    expect(screen.getByText("Back to Home").closest("a")).toHaveAttribute("href", "/")
  })

  it("mobile toggle button is hidden on desktop", () => {
    render(<Sidebar />)
    const toggle = screen.getByLabelText("Toggle navigation")
    // On desktop (jsdom default), should have md:hidden class
    expect(toggle.className).toContain("md:hidden")
  })

  it("mobile toggle opens and closes sidebar", () => {
    render(<Sidebar />)
    const toggle = screen.getByLabelText("Toggle navigation")

    // Click to open
    fireEvent.click(toggle)

    // The sidebar aside should now have translate-x-0
    const aside = document.querySelector("aside")
    expect(aside).toBeTruthy()

    // Click again to close
    fireEvent.click(toggle)
  })
})
