'use client'

import { useEffect, useRef, useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import { Activity, TrendingUp, Zap, Wifi, WifiOff, Circle } from 'lucide-react'
import clsx from 'clsx'

interface Tick  { time: string; total: number }
interface Metrics {
  ts: number
  total_per_sec: number
  per_symbol: Record<string, number>
  prices: Record<string, number>
  kafka_live: boolean
}

const SYM_COLOR: Record<string, string> = {
  BTCUSDT: '#F7931A',
  ETHUSDT: '#627EEA',
  BNBUSDT: '#F3BA2F',
  SOLUSDT: '#9945FF',
  ADAUSDT: '#0D6EFD',
  DOGEUSDT: '#C2A633',
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [history, setHistory] = useState<Tick[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    function connect() {
      const ws = new WebSocket('ws://localhost:8000/ws/metrics')
      wsRef.current = ws
      ws.onopen  = () => setConnected(true)
      ws.onclose = () => { setConnected(false); setTimeout(connect, 2000) }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        const data: Metrics = JSON.parse(e.data)
        setMetrics(data)
        setHistory(prev => [
          ...prev.slice(-59),
          { time: new Date().toLocaleTimeString('en', { hour12: false }), total: data.total_per_sec },
        ])
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const symbols  = metrics ? Object.keys(metrics.per_symbol).sort() : []
  const btcPrice = metrics?.prices?.['BTCUSDT']

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            Dashboard
          </h1>
          <p className="text-sm text-gray-500 mt-1">Real-time market monitoring</p>
        </div>
        <div className={clsx(
          'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border',
          connected
            ? 'border-green-500/20 bg-green-500/10 text-green-400'
            : 'border-red-500/20  bg-red-500/10  text-red-400',
        )}>
          {connected ? <Wifi size={11} /> : <WifiOff size={11} />}
          {connected ? 'Connected' : 'Reconnecting…'}
        </div>
      </div>

      {/* Top stat cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard
          icon={<Activity size={16} className="text-[#ff8432]" />}
          label="Messages / sec"
          value={metrics?.total_per_sec ?? 0}
          unit="msg/s"
          accent
        />
        <StatCard
          icon={<TrendingUp size={16} className="text-blue-400" />}
          label="Active symbols"
          value={symbols.length}
          unit="pairs"
        />
        <StatCard
          icon={<Zap size={16} className="text-yellow-400" />}
          label="BTC Price"
          value={btcPrice ? `$${btcPrice.toLocaleString('en', { maximumFractionDigits: 0 })}` : '—'}
          unit=""
        />
      </div>

      {/* Live area chart */}
      <div className="bg-[#171717] border border-white/[0.06] rounded-2xl p-6 mb-6 card-hover">
        <div className="flex items-end justify-between mb-6">
          <div>
            <p className="text-[11px] text-gray-600 uppercase tracking-widest font-medium mb-1">
              Messages per second — last 60 s
            </p>
            <p
              className="text-4xl font-black text-white glow-orange inline-block"
              style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
            >
              {metrics?.total_per_sec ?? 0}
            </p>
            <span className="text-gray-500 text-lg ml-2">msg/s</span>
          </div>
          <span className="text-[11px] text-gray-600 pb-1">Auto-refreshes every second</span>
        </div>

        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={history} margin={{ top: 4, right: 0, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#ff6207" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#ff6207" stopOpacity={0}    />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="time"
              tick={{ fill: '#4B5563', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: '#4B5563', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                background: '#1e1e1e',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 8,
                color: '#fff',
                fontSize: 12,
              }}
              cursor={{ stroke: 'rgba(255,98,7,0.25)', strokeWidth: 1 }}
            />
            <Area
              type="monotone"
              dataKey="total"
              stroke="#ff6207"
              strokeWidth={2}
              fill="url(#grad)"
              dot={false}
              activeDot={{ r: 4, fill: '#ff6207' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Per-symbol cards */}
      {symbols.length > 0 && (
        <div>
          <p className="text-[11px] text-gray-600 uppercase tracking-widest font-medium mb-3">
            Symbol breakdown
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
            {symbols.map(sym => {
              const color  = SYM_COLOR[sym] || '#ff6207'
              const ticker = sym.replace('USDT', '')
              const price  = metrics?.prices[sym]
              const count  = metrics?.per_symbol[sym] ?? 0
              return (
                <div
                  key={sym}
                  className="bg-[#171717] border border-white/[0.06] rounded-xl p-4 card-hover"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className="text-xs font-bold tracking-wide"
                      style={{ fontFamily: 'Switzer, Inter, sans-serif', color }}
                    >
                      {ticker}
                    </span>
                    <Circle size={7} fill={color} stroke="none" className="animate-pulse" />
                  </div>
                  <p
                    className="text-2xl font-black text-white"
                    style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
                  >
                    {count}
                  </p>
                  <p className="text-[11px] text-gray-600 mt-0.5">msg / s</p>
                  {price != null && (
                    <p className="text-xs text-gray-400 mt-2 font-mono">
                      ${price.toLocaleString('en', { maximumFractionDigits: 2 })}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({
  icon, label, value, unit, accent,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  unit: string
  accent?: boolean
}) {
  return (
    <div className={clsx(
      'bg-[#171717] border rounded-xl p-5 card-hover',
      accent ? 'border-[#ff6207]/20' : 'border-white/[0.06]',
    )}>
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p
        className="text-2xl font-bold text-white"
        style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
        {unit && <span className="text-sm font-normal text-gray-500 ml-1.5">{unit}</span>}
      </p>
    </div>
  )
}
