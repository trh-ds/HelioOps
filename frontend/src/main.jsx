import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './helio-globe.js' // registers <helio-globe> and pins window.THREE
import './index.css'
import About from './About.jsx'
import Dashboard from './Dashboard.jsx'
import Home from './Home.jsx'
import Industries from './Industries.jsx'
import Loader from './Loader.jsx'
import Problem from './Problem.jsx'
import SiteNav from './Nav.jsx'
import { Router, useRoute } from './router.jsx'

const PAGES = {
  '/': Home,
  '/about': About,
  '/problem': Problem,
  '/industries': Industries,
  '/dashboard': Dashboard
}

const LEAVE_MS = 200 // must match helioPageOut in index.css
const BOOT_MS = 4050 // must match the timeline at the top of loader.css
const REDUCE_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches

function App() {
  const { loc, path } = useRoute()
  // Plays once per page load, never on in-app navigation — this only mounts once.
  const [booting, setBooting] = useState(!REDUCE_MOTION)
  // `shown` lags `path` by one fade-out, so the outgoing page stays on screen
  // while it dims instead of being cut away the instant you click.
  const [shown, setShown] = useState(path)
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    if (path === shown) return
    setLeaving(true)
    // Batched, so the new page's first render already has is-leaving off.
    const t = setTimeout(() => {
      setShown(path)
      setLeaving(false)
    }, LEAVE_MS)
    return () => clearTimeout(t)
  }, [path, shown])

  useEffect(() => {
    if (!booting) return
    const done = () => setBooting(false)
    const t = setTimeout(done, BOOT_MS)
    window.addEventListener('pointerdown', done)
    window.addEventListener('keydown', done)
    return () => {
      clearTimeout(t)
      window.removeEventListener('pointerdown', done)
      window.removeEventListener('keydown', done)
    }
  }, [booting])

  // Scroll once the destination has committed — never mid-fade, or the page
  // you are still looking at jumps to the top as it dims.
  useEffect(() => {
    if (leaving) return
    const id = window.location.hash.slice(1)
    const el = id && document.getElementById(id)
    if (el) el.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [loc, shown, leaving])

  const Page = PAGES[shown] ?? Home
  return (
    <div className={booting ? 'app is-booting' : 'app'}>
      <SiteNav />
      <div className={leaving ? 'page-swap is-leaving' : 'page-swap'} key={shown}>
        <Page />
      </div>
      {booting && <Loader />}
    </div>
  )
}

// No StrictMode: its double effect pass would tear down and rebuild the WebGL
// context inside <helio-globe> on every mount.
createRoot(document.getElementById('root')).render(
  <Router>
    <App />
  </Router>
)
