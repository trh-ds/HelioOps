export default function Footer() {
  return (
    <footer className="relative z-20 border-t border-white/[0.04] bg-deep-black/90 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-aurora flex items-center justify-center">
              <span className="text-[8px] font-bold text-deep-black font-display">H</span>
            </div>
            <span className="text-xs text-white/30 font-body">&copy; 2024 HelioOps. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6">
            {["Privacy", "Terms", "Security"].map((l) => (
              <a key={l} href="#" className="text-xs text-white/25 hover:text-white/50 transition-colors duration-300 font-body">
                {l}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}