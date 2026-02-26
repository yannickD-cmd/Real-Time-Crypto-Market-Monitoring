'use client'

import { useEffect, useRef, useState } from 'react'
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
} from '@dnd-kit/core'
import {
  Upload, Search, Trash2, Send, X, UserPlus, Mail, GripVertical,
} from 'lucide-react'
import clsx from 'clsx'

const API = 'http://localhost:8000/api'

interface Member { id: string; name: string; email: string; tags: string[] }
interface Signal  { id: string; name: string; ticker: string }

export default function MembersPage() {
  const [members,        setMembers]        = useState<Member[]>([])
  const [signals,        setSignals]        = useState<Signal[]>([])
  const [query,          setQuery]          = useState('')
  const [recipients,     setRecipients]     = useState<Member[]>([])
  const [activeMember,   setActiveMember]   = useState<Member | null>(null)
  const [selectedSignal, setSelectedSignal] = useState('')
  const [subject,        setSubject]        = useState('')
  const [message,        setMessage]        = useState('')
  const [sending,        setSending]        = useState(false)
  const [sendResult,     setSendResult]     = useState<{ sent: number; errors: unknown[] } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  async function load() {
    const [mRes, sRes] = await Promise.all([
      fetch(`${API}/members/`),
      fetch(`${API}/signals/`),
    ])
    setMembers(await mRes.json())
    setSignals(await sRes.json())
  }
  useEffect(() => { load() }, [])

  async function handleCSV(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const res  = await fetch(`${API}/members/import-csv`, { method: 'POST', body: form })
    const data = await res.json()
    alert(`Imported ${data.imported} member${data.imported !== 1 ? 's' : ''} (${data.skipped} skipped as duplicates)`)
    load()
    e.target.value = ''
  }

  async function deleteMember(id: string) {
    await fetch(`${API}/members/${id}`, { method: 'DELETE' })
    setMembers(m => m.filter(x => x.id !== id))
    setRecipients(r => r.filter(x => x.id !== id))
  }

  function handleDragStart(e: DragStartEvent) {
    setActiveMember(members.find(x => x.id === e.active.id) ?? null)
  }

  function handleDragEnd(e: DragEndEvent) {
    setActiveMember(null)
    if (e.over?.id === 'dispatch-zone') {
      const m = members.find(x => x.id === e.active.id)
      if (m && !recipients.find(r => r.id === m.id)) {
        setRecipients(prev => [...prev, m])
      }
    }
  }

  async function sendDispatch() {
    if (!recipients.length || !subject || !message) return
    setSending(true)
    setSendResult(null)
    const sig = signals.find(s => s.id === selectedSignal)
    const res = await fetch(`${API}/dispatch/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipients,
        signal_name: sig?.name ?? 'Custom Alert',
        subject,
        message,
      }),
    })
    const data = await res.json()
    setSendResult(data)
    setSending(false)
    if (data.sent > 0) {
      setRecipients([])
      setSubject('')
      setMessage('')
    }
  }

  const recipientSet = new Set(recipients.map(r => r.id))
  const filtered     = members.filter(m =>
    m.name.toLowerCase().includes(query.toLowerCase()) ||
    m.email.toLowerCase().includes(query.toLowerCase()),
  )
  const canSend = recipients.length > 0 && subject.trim() && message.trim() && !sending

  return (
    <div className="p-8 h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            Members
          </h1>
          <p className="text-sm text-gray-500 mt-1">{members.length} community members</p>
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleCSV} />
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2 bg-[#171717] border border-white/[0.06] rounded-lg text-sm text-gray-300 hover:text-white hover:border-white/20 transition-all"
          >
            <Upload size={13} />
            Import CSV
          </button>
        </div>
      </div>

      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex gap-5" style={{ height: 'calc(100vh - 180px)' }}>

          {/* ── Left: member grid ── */}
          <div className="flex-1 flex flex-col min-w-0">
            <div className="relative mb-4">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search by name or email…"
                className="w-full pl-9 pr-4 py-2.5 bg-[#171717] border border-white/[0.06] rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#ff6207]/40 transition-colors"
              />
            </div>

            <div className="flex-1 overflow-y-auto pr-1">
              {filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-600">
                  <UserPlus size={32} className="mb-3 opacity-30" />
                  <p className="text-sm">No members yet.</p>
                  <p className="text-xs text-gray-700 mt-1">Import a CSV from Skool to get started.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 xl:grid-cols-3 gap-2.5">
                  {filtered.map(m => (
                    <DraggableMemberCard
                      key={m.id}
                      member={m}
                      inQueue={recipientSet.has(m.id)}
                      onDelete={() => deleteMember(m.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── Right: dispatch panel ── */}
          <div className="w-[300px] flex-shrink-0 flex flex-col gap-3">

            {/* Drop zone */}
            <DropZone
              recipients={recipients}
              onRemove={id => setRecipients(r => r.filter(x => x.id !== id))}
            />

            {/* Compose */}
            <div className="bg-[#171717] border border-white/[0.06] rounded-xl p-4 flex flex-col gap-3">
              <p className="text-[11px] text-gray-600 uppercase tracking-widest font-medium">
                Compose Alert
              </p>

              <select
                value={selectedSignal}
                onChange={e => setSelectedSignal(e.target.value)}
                className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white focus:outline-none focus:border-[#ff6207]/40 appearance-none"
              >
                <option value="">Select signal (optional)</option>
                {signals.map(s => (
                  <option key={s.id} value={s.id}>{s.name} ({s.ticker})</option>
                ))}
              </select>

              <input
                value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder="Email subject…"
                className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#ff6207]/40 transition-colors"
              />

              <textarea
                value={message}
                onChange={e => setMessage(e.target.value)}
                placeholder="Write your alert message…"
                rows={5}
                className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#ff6207]/40 resize-none transition-colors"
              />

              <button
                onClick={sendDispatch}
                disabled={!canSend}
                className={clsx(
                  'flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-semibold transition-all',
                  canSend
                    ? 'bg-[#ff6207] text-white hover:bg-[#cc4e06] shadow-lg shadow-[#ff6207]/20'
                    : 'bg-[#262626] text-gray-600 cursor-not-allowed',
                )}
              >
                <Send size={13} />
                {sending
                  ? 'Sending…'
                  : `Send to ${recipients.length} member${recipients.length !== 1 ? 's' : ''}`}
              </button>

              {sendResult && (
                <div className={clsx(
                  'text-xs px-3 py-2 rounded-lg border',
                  (sendResult.errors as unknown[]).length === 0
                    ? 'bg-green-500/10 text-green-400 border-green-500/20'
                    : 'bg-[#ff6207]/10 text-[#ff8432] border-[#ff6207]/20',
                )}>
                  ✓ Sent to {sendResult.sent} members
                  {(sendResult.errors as unknown[]).length > 0 && ` · ${(sendResult.errors as unknown[]).length} failed`}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Drag overlay ghost card */}
        <DragOverlay dropAnimation={null}>
          {activeMember && (
            <div className="bg-[#1e1e1e] border border-[#ff6207]/50 rounded-xl p-3 shadow-2xl shadow-black/60 rotate-1 w-52">
              <p className="text-sm font-medium text-white truncate">{activeMember.name}</p>
              <p className="text-xs text-gray-500 truncate">{activeMember.email}</p>
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  )
}

/* ─── Draggable member card ─── */
function DraggableMemberCard({
  member, inQueue, onDelete,
}: { member: Member; inQueue: boolean; onDelete: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: member.id,
    data: { member },
  })

  const initials = member.name
    .split(' ')
    .map(w => w[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2) || '?'

  return (
    <div
      ref={setNodeRef}
      className={clsx(
        'bg-[#171717] border rounded-xl p-3 select-none group transition-all card-hover',
        isDragging ? 'opacity-30 scale-95' : 'opacity-100',
        inQueue ? 'border-[#ff6207]/30' : 'border-white/[0.06]',
      )}
    >
      <div className="flex items-start gap-2.5">
        {/* Drag handle */}
        <div
          {...attributes}
          {...listeners}
          className="mt-0.5 cursor-grab active:cursor-grabbing p-0.5 text-gray-700 hover:text-gray-400 transition-colors flex-shrink-0"
        >
          <GripVertical size={13} />
        </div>

        {/* Avatar */}
        <div className="w-7 h-7 rounded-lg bg-[#262626] flex items-center justify-center text-[11px] font-bold text-[#ff8432] flex-shrink-0">
          {initials}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium text-white truncate leading-tight">{member.name}</p>
          <p className="text-[11px] text-gray-500 truncate">{member.email}</p>
        </div>

        {/* Delete */}
        <button
          onPointerDown={e => e.stopPropagation()}
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 p-1 text-gray-700 hover:text-red-400 transition-all rounded flex-shrink-0"
        >
          <Trash2 size={11} />
        </button>
      </div>

      {inQueue && (
        <div className="flex items-center gap-1 mt-2 ml-[46px]">
          <Mail size={9} className="text-[#ff8432]" />
          <span className="text-[10px] text-[#ff8432] font-medium">In dispatch</span>
        </div>
      )}
    </div>
  )
}

/* ─── Droppable dispatch zone ─── */
function DropZone({
  recipients, onRemove,
}: { recipients: Member[]; onRemove: (id: string) => void }) {
  const { isOver, setNodeRef } = useDroppable({ id: 'dispatch-zone' })

  return (
    <div
      ref={setNodeRef}
      className={clsx(
        'border-2 border-dashed rounded-xl p-4 transition-all flex flex-col',
        isOver
          ? 'border-[#ff6207]/70 bg-[#ff6207]/8'
          : 'border-white/10 bg-[#171717]',
        recipients.length === 0 ? 'items-center justify-center min-h-[130px]' : 'min-h-[130px]',
      )}
    >
      {recipients.length === 0 ? (
        <div className="text-center pointer-events-none">
          <div className={clsx(
            'w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-2 transition-colors',
            isOver ? 'bg-[#ff6207]/20' : 'bg-[#1e1e1e]',
          )}>
            <Mail size={17} className={isOver ? 'text-[#ff8432]' : 'text-gray-600'} />
          </div>
          <p className="text-xs text-gray-500">Drag members here</p>
          <p className="text-[11px] text-gray-700">to add as recipients</p>
        </div>
      ) : (
        <>
          <p className="text-[11px] text-gray-600 uppercase tracking-widest font-medium mb-2">
            Recipients ({recipients.length})
          </p>
          <div className="flex flex-col gap-1.5 overflow-y-auto max-h-[200px]">
            {recipients.map(r => (
              <div
                key={r.id}
                className="flex items-center justify-between bg-[#1e1e1e] rounded-lg px-2.5 py-1.5"
              >
                <div className="min-w-0">
                  <p className="text-[12px] font-medium text-white truncate">{r.name}</p>
                  <p className="text-[10px] text-gray-500 truncate">{r.email}</p>
                </div>
                <button
                  onClick={() => onRemove(r.id)}
                  className="ml-2 flex-shrink-0 text-gray-600 hover:text-red-400 transition-colors"
                >
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
