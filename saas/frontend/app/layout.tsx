import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Sidebar from '@/components/Sidebar'

const inter = Inter({ subsets: ['latin'], weight: ['300', '400', '500', '600', '700'] })

export const metadata: Metadata = {
  title: 'SignalDesk',
  description: 'Crypto community signal dispatcher',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <head>
        {/* Switzer from Fontshare — used for display headings */}
        <link
          rel="stylesheet"
          href="https://api.fontshare.com/v2/css?f[]=switzer@900,700,600,500,400&display=swap"
        />
      </head>
      <body style={{ background: '#0a0a0a' }}>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-[#0a0a0a]">{children}</main>
        </div>
      </body>
    </html>
  )
}
