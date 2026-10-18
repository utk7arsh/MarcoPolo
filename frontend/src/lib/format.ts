import type { DashboardData, Item } from './schema'

export function ago(at: string, now = Date.now()) {
  const minutes = Math.max(0, Math.floor((now - Date.parse(at)) / 60000))
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 1440)
    return `${Math.floor(minutes / 60)} ${minutes < 120 ? 'hour' : 'hours'} ago`
  return `${Math.floor(minutes / 1440)} ${minutes < 2880 ? 'day' : 'days'} ago`
}

export function direction(bearing: number) {
  const angle = (((bearing % 360) + 540) % 360) - 180
  if (Math.abs(angle) < 22.5) return 'Ahead of you'
  if (Math.abs(angle) > 157.5) return 'Behind you'
  const side = angle > 0 ? 'right' : 'left'
  if (Math.abs(angle) < 67.5) return `Ahead, to your ${side}`
  if (Math.abs(angle) > 112.5) return `Behind you, to your ${side}`
  return `To your ${side}`
}

export function location(item: Item) {
  return (
    item.lastSeen?.surface ||
    item.lastSeen?.roomName ||
    'Location not recorded yet'
  )
}

export function locationIsValid(data: DashboardData, item?: Item) {
  return !!(
    item?.lastSeen?.position &&
    item.lastSeen.worldMapId &&
    data.wearer &&
    data.session.worldMapId === item.lastSeen.worldMapId &&
    item.lastSeen.worldMapId === data.wearer.worldMapId
  )
}

export function currentMapWearer(data: DashboardData) {
  const mapId = data.session.worldMapId
  return mapId &&
    data.map?.worldMapId === mapId &&
    data.wearer?.worldMapId === mapId
    ? data.wearer
    : null
}

export function mapPositionIsLive(
  data: DashboardData,
  online: boolean,
  now = Date.now(),
) {
  const wearer = currentMapWearer(data)
  return !!(
    online &&
    wearer &&
    data.devices.phone.state === 'connected' &&
    data.devices.phone.tracking === 'normal' &&
    data.devices.phone.lastMessageAt &&
    now - Date.parse(data.devices.phone.lastMessageAt) < 5000 &&
    now - Date.parse(wearer.at) < 5000
  )
}

export function guidanceIssue(
  data: DashboardData,
  online: boolean,
  item?: Item,
  now = Date.now(),
) {
  if (!online) return 'Connection lost'
  if (data.devices.phone.state !== 'connected') return 'iPhone disconnected'
  if (
    !data.devices.phone.lastMessageAt ||
    now - Date.parse(data.devices.phone.lastMessageAt) > 5000
  )
    return 'Waiting for iPhone'
  if (data.devices.phone.tracking !== 'normal') return 'Restoring position'
  if (!locationIsValid(data, item)) return 'Location unavailable'
  if (now - Date.parse(data.wearer!.at) > 5000) return 'Waiting for position'
  return null
}

export function mediaUrl(path: string | null | undefined) {
  if (!path) return undefined
  if (/^https?:\/\//i.test(path)) return path
  if (path.startsWith('/') && !path.startsWith('//')) {
    if (
      import.meta.env.VITE_DATA_SOURCE !== 'api' ||
      !path.startsWith('/media/')
    )
      return path
    const base = import.meta.env.VITE_API_BASE_URL || '/api'
    return `${base.replace(/\/$/, '')}${path}`
  }
  return undefined
}
