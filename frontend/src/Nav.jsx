import { useEffect, useState } from 'react'
import { DASHBOARD_LINK, NAV } from './data.js'
import { Link, useRoute } from './router.jsx'

// Ignore sub-pixel jitter and trackpad bounce, and never hide while the bar is
// still over its own resting spot — otherwise it flickers at the top of a page.
const JITTER = 6
const ARM_AT = 120

/* One navbar, mounted once at the app root and never unmounted — that is what
   keeps it from moving or flickering while the page below it cross-fades.
   Pages must not render their own; they lay out below --nav-bottom instead. */
export default function SiteNav() {
  const { path } = useRoute()
  const [hidden, setHidden] = useState(false)

  // Home never scrolls (.home-stage is fixed), so this only ever fires on the
  // content pages — and scrollY stays 0 there, leaving the bar visible.
  useEffect(() => {
    let last = window.scrollY
    const onScroll = () => {
      const y = window.scrollY
      if (Math.abs(y - last) < JITTER) return
      setHidden(y > last && y > ARM_AT)
      last = y
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className={hidden ? 'navbar is-hidden' : 'navbar'}>
      <nav className="sitenav">
        <div className="sitenav-links">
          {NAV.map(n => (
            <Link key={n.label} to={n.to} className={n.path === path ? 'is-active' : undefined}>
              {n.label}
            </Link>
          ))}
        </div>
        <Link className="sitenav-cta" to={DASHBOARD_LINK}>
          OPEN DASHBOARD
        </Link>
      </nav>
    </div>
  )
}
