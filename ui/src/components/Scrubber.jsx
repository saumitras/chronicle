import { useRef, useEffect } from 'react'

export function Scrubber({ events, currentTs, onSeek, onPlay, isPlaying }) {
  const timestamps = events
    .filter(e => e.timestamp)
    .map(e => new Date(e.timestamp).getTime())
    .sort((a, b) => a - b)

  if (timestamps.length < 2) return null

  const minTs = timestamps[0]
  const maxTs = timestamps[timestamps.length - 1]
  const range = maxTs - minTs || 1
  const pct = currentTs ? Math.round(((currentTs - minTs) / range) * 100) : 100

  function handleSlider(e) {
    const val = Number(e.target.value)
    const ts = minTs + (val / 100) * range
    onSeek(ts)
  }

  return (
    <div className="shrink-0 px-4 py-2 bg-white border-t border-slate-200 flex items-center gap-3">
      <button onClick={onPlay}
        className="w-7 h-7 flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white rounded text-xs shrink-0">
        {isPlaying ? '⏸' : '▶'}
      </button>
      <input type="range" min={0} max={100} value={pct}
        onChange={handleSlider}
        className="flex-1 h-1.5 accent-blue-600 cursor-pointer" />
      <button onClick={() => onSeek(undefined)}
        className="px-2 py-1 text-xs bg-white border border-slate-200 text-slate-600 rounded hover:bg-slate-50 shrink-0">
        Live
      </button>
      <span className="text-xs text-slate-400 shrink-0">
        {currentTs ? new Date(currentTs).toLocaleTimeString() : 'Now'}
      </span>
    </div>
  )
}
