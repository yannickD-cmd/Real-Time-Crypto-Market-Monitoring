'use client'

import { useEffect, useState } from 'react'
import { Clock, ChevronRight, ChevronDown, Mail, AlertTriangle, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

const API = 'http://localhost:8000/api'

interface HistoryEntry {
  id: string
  ts: string
  signal_name: string
  subject: string
  message: string
  sent_to: string[]
  errors: { email: string; error: string }[]
  count: number
}

function fmtDate(ts: string) {
  try {
    return new Date(ts).toLocaleString('en', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
      hour12: false,
    })
  } catch { return ts }
}

export default function HistoryPage() {
  const [history,  setHistory]  = useState<HistoryEntry[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading,  setLoading]  = useState(true)

  async function load() {
    setLoading(true)
    const res = await fetch(`${API}/dispatch/history`)
    setHistory(await res.json())
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const total = history.reduce((acc, e) => acc + e.count, 0)

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            History
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {history.length} dispatches · {total} emails sent
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 bg-[#171717] border border-white/[0.06] rounded-lg text-sm text-gray-400 hover:text-white transition-all"
        >
          <RefreshCw size={13} className={clsx(loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Empty state */}
      {!loading && history.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 text-gray-600">
          <Clock size={32} className="mb-3 opacity-30" />
          <p className="text-sm">No alerts dispatched yet.</p>
          <p className="text-xs text-gray-700 mt-1">Go to Members → drag users → send an alert.</p>
        </div>
      )}

      {/* List */}
      <div className="space-y-2">
        {history.map(entry => (
          <div
            key={entry.id}
            className="bg-[#171717] border border-white/[0.06] rounded-xl overflow-hidden card-hover transition-all"
          >
            {/* Summary row */}
            <button
              onClick={() => setExpanded(e => e === entry.id ? null : entry.id)}
              className="w-full flex items-center gap-4 px-5 py-4 text-left"
            >
              <span className="text-gray-600 flex-shrink-0">
                {expanded === entry.id
                  ? <ChevronDown  size={13} />
                  : <ChevronRight size={13} />}
              </span>

              {/* Subject + badge */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <p className="text-[13.5px] font-medium text-white truncate">{entry.subject}</p>
                  <span className="flex-shrink-0 text-[10px] px-2 py-0.5 bg-[#ff6207]/10 text-[#ff8432] border border-[#ff6207]/20 rounded-full font-medium">
                    {entry.signal_name}
                  </span>
                </div>
                <p className="text-xs text-gray-500 truncate">{entry.message}</p>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-4 flex-shrink-0">
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Mail size={11} />
                  <span>{entry.count} sent</span>
                </div>
                {entry.errors.length > 0 && (
                  <div className="flex items-center gap-1 text-xs text-red-400">
                    <AlertTriangle size={11} />
                    <span>{entry.errors.length} failed</span>
                  </div>
                )}
                <span className="text-xs text-gray-600 w-28 text-right">{fmtDate(entry.ts)}</span>
              </div>
            </button>

            {/* Expanded detail */}
            {expanded === entry.id && (
              <div className="px-5 pb-5 border-t border-white/[0.06]">
                <div className="grid grid-cols-2 gap-4 pt-4">
                  {/* Sent to */}
                  <div>
                    <p className="text-[10px] text-gray-500 uppercase tracking-widest font-medium mb-2">
                      Sent to ({entry.sent_to.length})
                    </p>
                    <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
                      {entry.sent_to.map(email => (
                        <div
                          key={email}
                          className="flex items-center gap-2 text-xs text-gray-300 bg-[#1e1e1e] px-2.5 py-1.5 rounded-lg"
                        >
                          <Mail size={10} className="text-gray-600 flex-shrink-0" />
                          {email}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Right: message + errors */}
                  <div className="space-y-4">
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-widest font-medium mb-2">
                        Message
                      </p>
                      <p className="text-xs text-gray-400 bg-[#1e1e1e] px-3 py-2.5 rounded-lg whitespace-pre-wrap">
                        {entry.message}
                      </p>
                    </div>

                    {entry.errors.length > 0 && (
                      <div>
                        <p className="text-[10px] text-red-400 uppercase tracking-widest font-medium mb-2">
                          Failed ({entry.errors.length})
                        </p>
                        <div className="space-y-1">
                          {entry.errors.map((err, i) => (
                            <div
                              key={i}
                              className="text-xs bg-red-500/8 border border-red-500/20 px-2.5 py-1.5 rounded-lg"
                            >
                              <p className="text-red-300">{err.email}</p>
                              <p className="text-red-500 text-[10px] mt-0.5">{err.error}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
