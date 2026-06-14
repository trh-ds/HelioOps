import Sidebar from "@/components/dashboard/Sidebar"
import TopBar from "@/components/dashboard/TopBar"
import { ToastProvider } from "@/components/Toast"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden bg-deep-black">
        <Sidebar />

        {/* Main content area — offset by sidebar width on desktop */}
        <div className="flex flex-col flex-1 md:pl-60">
          <TopBar />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </div>
      </div>
    </ToastProvider>
  )
}
