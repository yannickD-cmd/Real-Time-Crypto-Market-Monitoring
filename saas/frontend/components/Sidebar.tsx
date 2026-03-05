'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Users, Radio, History, Zap, Layers } from 'lucide-react'
import clsx from 'clsx'

const nav = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/members',   icon: Users,           label: 'Members'   },
  { href: '/groups',    icon: Layers,          label: 'Groups'    },
  { href: '/signals',   icon: Radio,           label: 'Signals'   },
  { href: '/history',   icon: History,         label: 'History'   },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-[220px] flex-shrink-0 flex flex-col bg-[#0a0a0a] border-r border-white/[0.06]">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#ff6207] flex items-center justify-center shadow-lg shadow-[#ff6207]/30">
            <Zap size={13} className="text-white fill-white" />
          </div>
          <span
            className="font-semibold text-white tracking-tight text-[15px]"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            SignalDesk
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5">
        {nav.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || pathname.startsWith(href + '/')
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] font-medium transition-all duration-150',
                active
                  ? 'bg-[#ff6207]/10 text-[#ff8432] border border-[#ff6207]/20'
                  : 'text-gray-400 hover:text-white hover:bg-white/[0.04] border border-transparent',
              )}
            >
              <Icon size={15} strokeWidth={active ? 2.2 : 1.7} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer status */}
      <div className="px-5 py-4 border-t border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#ff6207] opacity-60" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#ff6207]" />
          </span>
          <span className="text-[11px] text-gray-500 font-medium">Live pipeline</span>
        </div>
      </div>
    </aside>
  )
}
