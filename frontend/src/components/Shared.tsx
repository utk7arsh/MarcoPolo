import { useEffect, useRef, useState } from 'react'
import type { Item } from '../lib/schema'
import { mediaUrl } from '../lib/format'
import { Icon } from './Icon'
import { itemIcon } from '../lib/itemIcon'

export function ItemImage({
  item,
  large = false,
}: {
  item: Pick<Item, 'name' | 'photoUrl'>
  large?: boolean
}) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const src = mediaUrl(item.photoUrl)
  return (
    <span className={`item-image ${large ? 'large' : ''}`}>
      {src && failedUrl !== src ? (
        <img src={src} alt="" onError={() => setFailedUrl(src)} />
      ) : (
        <Icon name={itemIcon(item.name)} size={large ? 38 : 28} />
      )}
    </span>
  )
}
export function EmptyState({
  icon = 'key',
  title,
  detail,
}: {
  icon?: Parameters<typeof Icon>[0]['name']
  title: string
  detail?: string
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={30} />
      </span>
      <h2>{title}</h2>
      {detail && <p>{detail}</p>}
    </div>
  )
}
export function VoiceLabel({ item }: { item: Item }) {
  const label = item.voiceLabel
  const url = mediaUrl(label?.audioUrl)
  if (!label) return null
  return (
    <div className="voice-label">
      {url ? (
        <VoicePlayer key={url} url={url} />
      ) : (
        label.transcript && <p className="transcript">{label.transcript}</p>
      )}
    </div>
  )
}

function VoicePlayer({ url }: { url: string }) {
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(false)
  const audio = useRef<HTMLAudioElement>(null)
  useEffect(() => {
    const element = audio.current
    return () => element?.pause()
  }, [])
  return (
    <>
      <audio
        ref={audio}
        src={url}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onError={() => setError(true)}
      />
      <button
        className="voice-button"
        aria-label={playing ? 'Pause voice label' : 'Play voice label'}
        disabled={error}
        onClick={() => {
          const element = audio.current!
          if (playing) element.pause()
          else void element.play().catch(() => setError(true))
        }}
      >
        <span className="play-circle">
          <Icon name={playing ? 'pause' : 'play'} size={15} />
        </span>
        <span>Voice label</span>
      </button>
      {error && (
        <span className="media-error" role="status">
          Audio unavailable
        </span>
      )}
    </>
  )
}
