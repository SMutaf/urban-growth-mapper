// Small monochrome outline icons (Google Maps-style) - inline SVG rather
// than an icon font/CDN, so the app stays self-contained. currentColor
// throughout so each icon inherits its button's text color.

const BASE_PROPS = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

export function SearchIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

export function MenuIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

export function CloseIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <line x1="6" y1="6" x2="18" y2="18" />
      <line x1="18" y1="6" x2="6" y2="18" />
    </svg>
  )
}

export function SchoolIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <path d="M2 9.5 12 5l10 4.5-10 4.5L2 9.5Z" />
      <path d="M6 11.5V17c0 1.1 2.7 2.5 6 2.5s6-1.4 6-2.5v-5.5" />
      <line x1="21" y1="9.5" x2="21" y2="16" />
    </svg>
  )
}

export function HospitalIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <rect x="3" y="4" width="18" height="17" rx="1.5" />
      <line x1="12" y1="9" x2="12" y2="15" />
      <line x1="9" y1="12" x2="15" y2="12" />
    </svg>
  )
}

export function BusIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <rect x="3" y="5" width="18" height="12" rx="2" />
      <line x1="3" y1="11" x2="21" y2="11" />
      <line x1="7" y1="8" x2="7" y2="8" />
      <circle cx="7.5" cy="19" r="1.5" />
      <circle cx="16.5" cy="19" r="1.5" />
    </svg>
  )
}

export function PinIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </svg>
  )
}

export function ChatIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} {...BASE_PROPS}>
      <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z" />
    </svg>
  )
}
