import type { IconName } from '../components/Icon'
export function itemIcon(name: string): IconName {
  if (/key/i.test(name)) return 'key'
  if (/mug|cup|bottle/i.test(name)) return 'mug'
  if (/glass/i.test(name)) return 'glasses'
  if (/wallet/i.test(name)) return 'wallet'
  return 'object'
}
