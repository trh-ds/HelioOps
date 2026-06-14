import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import StormsPage from "@/app/dashboard/storms/page"

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/storms",
}))

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const mockAddToast = vi.fn()
vi.mock("@/components/Toast", () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useToast: () => ({ addToast: mockAddToast, dismissToast: vi.fn() }),
}))

const mockGetStorms = vi.fn()
vi.mock("@/lib/api", () => ({
  api: {
    getStorms: () => mockGetStorms(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

describe("StormsPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("shows loading skeleton initially", () => {
    mockGetStorms.mockReturnValue(new Promise(() => {}))
    render(<StormsPage />)
    expect(screen.getAllByRole("generic").length).toBeGreaterThan(0)
  })

  it("renders storm cards after loading", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: ["2024-10-G4", "2024-05-G5"],
      completed: {},
    })

    render(<StormsPage />)

    await waitFor(() => {
      expect(screen.getByText("2024-10-G4")).toBeInTheDocument()
      expect(screen.getByText("2024-05-G5")).toBeInTheDocument()
    })
  })

  it("shows error state on API failure", async () => {
    mockGetStorms.mockRejectedValue(new Error("Network error"))

    render(<StormsPage />)

    await waitFor(() => {
      expect(screen.getByText("Failed to load storms")).toBeInTheDocument()
    })
  })

  it("shows empty state when no storms", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: [],
      completed: {},
    })

    render(<StormsPage />)

    await waitFor(() => {
      expect(screen.getByText("No storms available.")).toBeInTheDocument()
    })
  })

  it("renders page heading", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: [],
      completed: {},
    })

    render(<StormsPage />)

    await waitFor(() => {
      expect(screen.getByText("Storm List")).toBeInTheDocument()
    })
  })
})
