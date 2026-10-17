import { useState } from 'react'
import type { DashboardData } from '../lib/schema'
import { locationIsValid } from '../lib/format'
import { Icon } from './Icon'
import { itemIcon } from '../lib/itemIcon'
import { EmptyState } from './Shared'

export function MapView({
  data,
  live,
  targetId,
}: {
  data: DashboardData
  live: boolean
  targetId: string | null
}) {
  const [centered, setCentered] = useState(false)
  const map = data.map
  if (!map)
    return (
      <div className="map-absent">
        <EmptyState icon="map" title="Map unavailable" />
      </div>
    )
  const { bounds: b } = map
  const width = b.maxX - b.minX
  const depth = b.maxZ - b.minZ
  const scale = Math.min(650 / width, 440 / depth)
  const x = (value: number) => 400 + (value - (b.minX + b.maxX) / 2) * scale
  const z = (value: number) => 260 + (value - (b.minZ + b.maxZ) / 2) * scale
  const wearer = data.wearer?.worldMapId === map.worldMapId ? data.wearer : null
  const target = data.items.find((item) => item.id === targetId)
  const targetPosition =
    target && locationIsValid(data, target) ? target.lastSeen?.position : null
  const validItems = data.items.filter(
    (item) =>
      item.lastSeen?.position && item.lastSeen.worldMapId === map.worldMapId,
  )
  const offset =
    centered && wearer
      ? { x: 400 - x(wearer.position.x), z: 260 - z(wearer.position.z) }
      : { x: 0, z: 0 }
  return (
    <>
      <div className="map-canvas">
        <svg
          className="room-map"
          viewBox={`${x(b.minX) - 40} ${z(b.minZ) - 35} ${width * scale + 80} ${depth * scale + 90}`}
          role="img"
          aria-label={`Room map, ${validItems.length} remembered objects${live && wearer ? ', current position' : ''}`}
        >
          <g transform={`translate(${offset.x} ${offset.z})`}>
            <rect
              x={x(b.minX)}
              y={z(b.minZ)}
              width={width * scale}
              height={depth * scale}
              fill="#fafafa"
            />
            {map.walls?.map((wall, i) => (
              <line
                key={i}
                x1={x(wall.from.x)}
                y1={z(wall.from.z)}
                x2={x(wall.to.x)}
                y2={z(wall.to.z)}
                stroke="#c9ccd2"
                strokeWidth="3.5"
              />
            ))}
            <text x={x(b.minX) + 25} y={z(b.minZ) + 31} className="room-label">
              {data.session.roomName.toUpperCase()}
            </text>
            {map.fixtures?.map((fixture) => (
              <g key={fixture.id}>
                <rect
                  x={x(fixture.x)}
                  y={z(fixture.z)}
                  width={fixture.width * scale}
                  height={fixture.depth * scale}
                  rx={fixture.kind === 'table' ? 32 : 12}
                  fill={fixture.kind === 'table' ? '#eeede8' : '#eaeae7'}
                  stroke="#deddd6"
                />
                {fixture.kind === 'sofa' && (
                  <rect
                    x={x(fixture.x) + 12}
                    y={z(fixture.z) + 12}
                    width={fixture.width * scale - 24}
                    height={fixture.depth * scale - 24}
                    rx="9"
                    fill="#f2f2ef"
                    stroke="#e2e2dd"
                  />
                )}
                {fixture.kind === 'table' && (
                  <text
                    x={x(fixture.x + fixture.width / 2)}
                    y={z(fixture.z + fixture.depth) + 28}
                    textAnchor="middle"
                    className="surface-label"
                  >
                    {fixture.name}
                  </text>
                )}
              </g>
            ))}
            {live && wearer && targetPosition && (
              <line
                x1={x(wearer.position.x)}
                y1={z(wearer.position.z)}
                x2={x(targetPosition.x)}
                y2={z(targetPosition.z)}
                stroke="#9cb8d8"
                strokeDasharray="4 7"
                strokeWidth="1.5"
              />
            )}
            {validItems.map((item) => {
              const p = item.lastSeen!.position!
              const selected = item.id === targetId
              return (
                <g key={item.id} transform={`translate(${x(p.x)} ${z(p.z)})`}>
                  {selected && <circle r="30" fill="#0066cc" opacity=".055" />}
                  <circle
                    r={selected ? 19 : 13}
                    fill="white"
                    stroke={selected ? '#0066cc' : '#c9ccd2'}
                    strokeWidth={selected ? 1.8 : 1}
                  />
                  <g
                    transform={`translate(${selected ? -9 : -7} ${selected ? -9 : -7})`}
                    color={selected ? '#0066cc' : '#767b82'}
                  >
                    <Icon
                      name={itemIcon(item.name)}
                      size={selected ? 18 : 14}
                    />
                  </g>
                  {selected && (
                    <>
                      <rect
                        x={-Math.max(68, item.name.length * 7 + 20) / 2}
                        y="32"
                        width={Math.max(68, item.name.length * 7 + 20)}
                        height="26"
                        rx="13"
                        fill="white"
                        stroke="#e4e6eb"
                      />
                      <text y="49" textAnchor="middle" className="target-label">
                        {item.name}
                      </text>
                    </>
                  )}
                </g>
              )
            })}
            {live && wearer && (
              <g
                transform={`translate(${x(wearer.position.x)} ${z(wearer.position.z)})`}
              >
                <path
                  d="M0 0 -25 -65 25 -65Z"
                  fill="#0066cc"
                  opacity=".065"
                  transform={`rotate(${wearer.bodyYawDeg})`}
                />
                <circle r="18" fill="#0066cc" opacity=".08" />
                <circle r="10" fill="#0066cc" stroke="white" strokeWidth="4" />
                <text y="34" textAnchor="middle" className="surface-label">
                  You
                </text>
              </g>
            )}
          </g>
        </svg>
      </div>
      <div className="map-footer">
        <div className="map-legend">
          <span>
            <i className={`dot ${live ? 'blue' : 'gray'}`} />
            You
          </span>
          <span>
            <i className="ring-dot" />
            Remembered objects
          </span>
        </div>
        <button
          className="text-button"
          disabled={!live || !wearer}
          aria-pressed={centered}
          onClick={() => setCentered(!centered)}
        >
          <Icon name="recenter" size={16} />
          Recenter
        </button>
      </div>
    </>
  )
}
