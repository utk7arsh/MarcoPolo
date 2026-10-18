import type { CSSProperties } from 'react'

export type IconName =
  | 'object'
  | 'key'
  | 'mug'
  | 'glasses'
  | 'wallet'
  | 'search'
  | 'chevron'
  | 'arrow'
  | 'speaker'
  | 'play'
  | 'pause'
  | 'stop'
  | 'check'
  | 'close'
  | 'recenter'
  | 'info'
  | 'camera'
  | 'map'
  | 'phone'
  | 'refresh'
  | 'signal'
const paths: Record<IconName, React.ReactNode> = {
  object: (
    <>
      <path d="m12 3 9 5v9l-9 5-9-5V8l9-5Zm0 9 9-4M12 12 3 8m9 4v10" />
    </>
  ),
  key: (
    <>
      <circle cx="9" cy="9" r="5" />
      <path d="m12.5 12.5 8 8m-3-3 2-2m-5 2 2-2" />
    </>
  ),
  mug: (
    <>
      <path d="M4 8h12v9a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8Zm12 1h2a3 3 0 0 1 0 6h-2M7 3v2m5-2v2" />
    </>
  ),
  glasses: (
    <>
      <circle cx="6" cy="15" r="4" />
      <circle cx="18" cy="15" r="4" />
      <path d="M10 15a2 2 0 0 1 4 0M2 14l2-9h3m15 9-2-9h-3" />
    </>
  ),
  wallet: (
    <>
      <rect x="3" y="5" width="18" height="15" rx="3" />
      <path d="M3 9h18m0 4h-7v4h7m-5-2h1" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  chevron: <path d="m9 6 6 6-6 6" />,
  arrow: <path d="M12 21V3m-7 7 7-7 7 7" />,
  speaker: (
    <>
      <path d="m11 4-6 5H2v6h3l6 5V4Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" />
    </>
  ),
  play: <path d="m9 5 11 7L9 19V5Z" />,
  stop: <rect x="7" y="7" width="10" height="10" rx="1" fill="currentColor" />,
  pause: (
    <>
      <path d="M8 5v14m8-14v14" />
    </>
  ),
  check: <path d="m5 12 5 5L20 7" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  recenter: (
    <>
      <circle cx="12" cy="12" r="6" />
      <path d="M12 2v3m0 14v3M2 12h3m14 0h3" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6m0-10v.1" />
    </>
  ),
  camera: (
    <>
      <rect x="2" y="6" width="20" height="15" rx="3" />
      <circle cx="12" cy="13" r="4" />
      <path d="m7 6 2-3h6l2 3" />
    </>
  ),
  map: (
    <>
      <path d="m9 3-7 3v15l7-3 6 3 7-3V3l-7 3-6-3Zm0 0v15m6-12v15" />
    </>
  ),
  phone: (
    <>
      <rect x="6" y="2" width="12" height="20" rx="3" />
      <path d="M11 18h2" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 7V2l-3 3a8 8 0 1 0 3 11M20 7h-5" />
    </>
  ),
  signal: (
    <>
      <path d="M4 18v2m5-7v7m5-12v12m5-17v17" />
    </>
  ),
}
export function Icon({
  name,
  size = 20,
  style,
  className = '',
}: {
  name: IconName
  size?: number
  style?: CSSProperties
  className?: string
}) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      className={className}
    >
      {paths[name]}
    </svg>
  )
}
