'use client'

import { useEffect, useState } from 'react'
import { Plus, Trash2, ToggleLeft, ToggleRight, Radio } from 'lucide-react'
import clsx from 'clsx'

const API = 'http://localhost:8000/api'

interface Signal {
  id: string
  symbol: string
  name: string
  ticker: string
  enabled: boolean
  threshold_vol: number
  threshold_spread: number
  color: string
}

const PRESETS = [
  { symbol: 'SOLUSDT',  name: 'Solana',    ticker: 'SOL',  color: '#9945FF' },
  { symbol: 'ADAUSDT',  name: 'Cardano',   ticker: 'ADA',  color: '#0D6EFD' },
  { symbol: 'DOGEUSDT', name: 'Dogecoin',  ticker: 'DOGE', color: '#C2A633' },
  { symbol: 'XRPUSDT',  name: 'Ripple',    ticker: 'XRP',  color: '#346AA9' },
  { symbol: 'AVAXUSDT', name: 'Avalanche', ticker: 'AVAX', color: '#E84142' },
  { symbol: 'LINKUSDT', name: 'Chainlink', ticker: 'LINK', color: '#2A5ADA' },
]

const EMPTY_FORM = {
  symbol: '', name: '', ticker: '', color: '#ff6207',
  threshold_vol: 2.0, threshold_spread: 3.0,
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [form,    setForm]    = useState(EMPTY_FORM)
  const [saving,  setSaving]  = useState(false)
  const [error,   setError]   = useState('')

  async function fetchSignals() {
    const res = await fetch(`${API}/signals/`)
    setSignals(await res.json())
  }
  useEffect(() => { fetchSignals() }, [])

  async function toggleSignal(id: string, enabled: boolean) {
    await fetch(`${API}/signals/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    setSignals(s => s.map(x => x.id === id ? { ...x, enabled } : x))
  }

  async function deleteSignal(id: string) {
    if (!confirm('Remove this signal?')) return
    await fetch(`${API}/signals/${id}`, { method: 'DELETE' })
    setSignals(s => s.filter(x => x.id !== id))
  }

  async function addSignal() {
    if (!form.symbol || !form.name || !form.ticker) {
      setError('Symbol, name, and ticker are required.')
      return
    }
    setSaving(true)
    setError('')
    const res = await fetch(`${API}/signals/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (res.ok) {
      setSignals(s => [...s, await res.json()])
      setShowAdd(false)
      setForm(EMPTY_FORM)
    } else {
      const d = await res.json()
      setError(d.detail ?? 'Failed to add signal.')
    }
    setSaving(false)
  }

  function applyPreset(p: typeof PRESETS[0]) {
    setForm(f => ({ ...f, ...p }))
    setError('')
  }

  const active = signals.filter(s => s.enabled).length
  const paused = signals.filter(s => !s.enabled).length

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            Signals
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {active} active · {paused} paused
          </p>
        </div>
        <button
          onClick={() => { setShowAdd(v => !v); setError('') }}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all',
            showAdd
              ? 'bg-[#1e1e1e] text-gray-400 border border-white/[0.06]'
              : 'bg-[#ff6207] text-white hover:bg-[#cc4e06] shadow-lg shadow-[#ff6207]/20',
          )}
        >
          <Plus size={14} className={clsx('transition-transform', showAdd && 'rotate-45')} />
          {showAdd ? 'Cancel' : 'Add Signal'}
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="bg-[#171717] border border-[#ff6207]/20 rounded-2xl p-5 mb-6">
          <p className="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-4">
            New Signal
          </p>

          {/* Presets */}
          <div className="mb-4">
            <p className="text-xs text-gray-600 mb-2">Quick add a preset</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map(p => (
                <button
                  key={p.symbol}
                  onClick={() => applyPreset(p)}
                  className={clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all',
                    form.symbol === p.symbol
                      ? 'bg-[#ff6207]/15 border border-[#ff6207]/30 text-[#ff8432]'
                      : 'bg-[#1e1e1e] border border-white/[0.06] text-gray-300 hover:text-white hover:border-white/20',
                  )}
                >
                  <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: p.color }} />
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 mb-3">
            {[
              { label: 'Binance Symbol', key: 'symbol', placeholder: 'SOLUSDT', upper: true },
              { label: 'Name',           key: 'name',   placeholder: 'Solana'                },
              { label: 'Ticker',         key: 'ticker', placeholder: 'SOL',     upper: true  },
            ].map(({ label, key, placeholder, upper }) => (
              <div key={key}>
                <label className="text-[11px] text-gray-500 mb-1.5 block">{label}</label>
                <input
                  value={(form as Record<string, unknown>)[key] as string}
                  onChange={e => setForm(f => ({
                    ...f,
                    [key]: upper ? e.target.value.toUpperCase() : e.target.value,
                  }))}
                  placeholder={placeholder}
                  className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#ff6207]/40 transition-colors"
                />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-3 mb-4">
            <div>
              <label className="text-[11px] text-gray-500 mb-1.5 block">Volatility threshold (σ)</label>
              <input
                type="number" step="0.1" value={form.threshold_vol}
                onChange={e => setForm(f => ({ ...f, threshold_vol: parseFloat(e.target.value) }))}
                className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white focus:outline-none focus:border-[#ff6207]/40"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1.5 block">Spread threshold (×)</label>
              <input
                type="number" step="0.5" value={form.threshold_spread}
                onChange={e => setForm(f => ({ ...f, threshold_spread: parseFloat(e.target.value) }))}
                className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white focus:outline-none focus:border-[#ff6207]/40"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1.5 block">Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color" value={form.color}
                  onChange={e => setForm(f => ({ ...f, color: e.target.value }))}
                  className="w-10 h-9 rounded-lg border border-white/[0.06] bg-transparent cursor-pointer"
                />
                <span className="text-xs text-gray-500 font-mono">{form.color}</span>
              </div>
            </div>
          </div>

          {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

          <div className="flex justify-end">
            <button
              onClick={addSignal}
              disabled={saving}
              className="px-5 py-2 bg-[#ff6207] text-white rounded-lg text-sm font-semibold hover:bg-[#cc4e06] transition-colors disabled:opacity-50"
            >
              {saving ? 'Adding…' : 'Add Signal'}
            </button>
          </div>
        </div>
      )}

      {/* Signal list */}
      <div className="space-y-2">
        {signals.length === 0 && !showAdd && (
          <div className="flex flex-col items-center justify-center h-48 text-gray-600">
            <Radio size={28} className="mb-3 opacity-30" />
            <p className="text-sm">No signals yet.</p>
          </div>
        )}
        {signals.map(sig => (
          <SignalRow
            key={sig.id}
            signal={sig}
            onToggle={enabled => toggleSignal(sig.id, enabled)}
            onDelete={() => deleteSignal(sig.id)}
          />
        ))}
      </div>
    </div>
  )
}

function SignalRow({
  signal: s, onToggle, onDelete,
}: { signal: Signal; onToggle: (v: boolean) => void; onDelete: () => void }) {
  return (
    <div className={clsx(
      'bg-[#171717] border rounded-xl px-5 py-4 flex items-center gap-4 card-hover transition-all',
      s.enabled ? 'border-white/[0.06]' : 'border-white/[0.03] opacity-55',
    )}>
      {/* Color + Name */}
      <div className="flex items-center gap-3 w-44 flex-shrink-0">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: s.color + '22' }}
        >
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} />
        </div>
        <div>
          <p
            className="text-sm font-bold text-white leading-tight"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            {s.name}
          </p>
          <p className="text-[11px] text-gray-500 font-mono">{s.symbol}</p>
        </div>
      </div>

      {/* Thresholds */}
      <div className="flex gap-6 flex-1">
        <div>
          <p className="text-[10px] text-gray-600 uppercase tracking-wide">Volatility</p>
          <p className="text-sm text-white font-medium">σ {s.threshold_vol}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-600 uppercase tracking-wide">Spread</p>
          <p className="text-sm text-white font-medium">× {s.threshold_spread}</p>
        </div>
      </div>

      {/* Status badge */}
      <div className="flex-shrink-0">
        {s.enabled ? (
          <span className="inline-flex items-center gap-1.5 text-[11px] text-green-400 bg-green-500/10 border border-green-500/20 px-2.5 py-1 rounded-full font-medium">
            <Radio size={9} />Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-[11px] text-gray-500 bg-white/[0.03] border border-white/[0.06] px-2.5 py-1 rounded-full font-medium">
            Paused
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={() => onToggle(!s.enabled)}
          className="p-2 rounded-lg hover:bg-white/[0.04] transition-colors"
        >
          {s.enabled
            ? <ToggleRight size={20} className="text-[#ff8432]" />
            : <ToggleLeft  size={20} className="text-gray-600"  />}
        </button>
        <button
          onClick={onDelete}
          className="p-2 rounded-lg hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}
