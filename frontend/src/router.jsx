import { createContext, useCallback, useContext, useEffect, useState } from 'react'

/* A four-page static site does not need a routing library: pushState, popstate
   and one anchor-scroll effect cover every navigation this app can perform. */

const RouteContext = createContext(null)

const here = () => window.location.pathname + window.location.hash

export function Router({ children }) {
  const [loc, setLoc] = useState(here)

  useEffect(() => {
    const onPop = () => setLoc(here())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const navigate = useCallback(to => {
    if (to === here()) return
    window.history.pushState(null, '', to)
    setLoc(to)
  }, [])

  // `loc` carries the hash too: App scrolls off it, and must, since a hash-only
  // jump leaves `path` unchanged.
  return (
    <RouteContext.Provider value={{ loc, path: loc.split('#')[0], navigate }}>
      {children}
    </RouteContext.Provider>
  )
}

export const useRoute = () => useContext(RouteContext)

export function Link({ to, children, ...rest }) {
  const { navigate } = useRoute()
  return (
    <a
      href={to}
      onClick={e => {
        // let the browser handle new-tab / new-window modifiers
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
        e.preventDefault()
        navigate(to)
      }}
      {...rest}
    >
      {children}
    </a>
  )
}
