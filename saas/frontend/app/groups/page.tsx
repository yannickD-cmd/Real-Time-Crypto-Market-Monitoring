'use client'

import { useEffect, useState } from 'react'
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
  Users, Radio, Plus, Trash2, GripVertical, Layers, X, Check,
} from 'lucide-react'
import clsx from 'clsx'

const API = 'http://localhost:8000/api'

interface Group {
  id: string
  name: string
  color: string
  signal_ids: string[]
  member_ids: string[]
}

interface Member {
  id: string
  name: string
  email: string
  tags: string[]
}

interface Signal {
  id: string
  symbol: string
  name: string
  ticker: string
  color: string
  enabled: boolean
}

const GROUP_COLORS = [
  '#ff6207', '#627EEA', '#F7931A', '#9945FF',
  '#0D6EFD', '#E84142', '#F3BA2F', '#2A5ADA',
]

export default function GroupsPage() {
  const [groups, setGroups]   = useState<Group[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [activeTab, setActiveTab] = useState<'members' | 'signals'>('members')
  const [activeDrag, setActiveDrag] = useState<Member | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName]   = useState('')
  const [newColor, setNewColor] = useState(GROUP_COLORS[0])
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  async function load() {
    const [gRes, mRes, sRes] = await Promise.all([
      fetch(`${API}/groups/`),
      fetch(`${API}/members/`),
      fetch(`${API}/signals/`),
    ])
    setGroups(await gRes.json())
    setMembers(await mRes.json())
    setSignals(await sRes.json())
  }

  useEffect(() => { load() }, [])

  async function createGroup() {
    if (!newName.trim()) { setCreateError('Name is required'); return }
    setCreating(true)
    setCreateError('')
    const res = await fetch(`${API}/groups/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName.trim(), color: newColor }),
    })
    if (res.ok) {
      const g = await res.json()
      setGroups(prev => [...prev, g])
      setNewName('')
      setShowCreate(false)
    } else {
      const d = await res.json()
      setCreateError(d.detail ?? 'Failed to create group')
    }
    setCreating(false)
  }

  async function deleteGroup(id: string) {
    if (!confirm('Delete this group? Members will become unassigned.')) return
    await fetch(`${API}/groups/${id}`, { method: 'DELETE' })
    setGroups(prev => prev.filter(g => g.id !== id))
  }

  // Find which group a member currently belongs to
  function memberGroupId(memberId: string): string | null {
    return groups.find(g => g.member_ids.includes(memberId))?.id ?? null
  }

  function handleDragStart(e: DragStartEvent) {
    const m = members.find(x => x.id === e.active.id)
    setActiveDrag(m ?? null)
  }

  async function handleDragEnd(e: DragEndEvent) {
    setActiveDrag(null)
    if (!e.over) return
    const memberId  = e.active.id as string
    const targetId  = e.over.id  as string   // group id OR 'unassigned'
    const sourceId  = memberGroupId(memberId)

    if (targetId === sourceId) return
    if (targetId === (sourceId ?? 'unassigned')) return

    // Optimistic update
    setGroups(prev => prev.map(g => {
      const withoutMember = { ...g, member_ids: g.member_ids.filter(id => id !== memberId) }
      if (g.id === targetId) {
        return { ...withoutMember, member_ids: [...withoutMember.member_ids, memberId] }
      }
      return withoutMember
    }))

    // API calls
    if (sourceId) {
      await fetch(`${API}/groups/${sourceId}/members/${memberId}`, { method: 'DELETE' })
    }
    if (targetId !== 'unassigned') {
      await fetch(`${API}/groups/${targetId}/members/${memberId}`, { method: 'POST' })
    }
  }

  async function toggleSignal(groupId: string, signalId: string, hasIt: boolean) {
    const method = hasIt ? 'DELETE' : 'POST'
    await fetch(`${API}/groups/${groupId}/signals/${signalId}`, { method })
    setGroups(prev => prev.map(g => {
      if (g.id !== groupId) return g
      return {
        ...g,
        signal_ids: hasIt
          ? g.signal_ids.filter(s => s !== signalId)
          : [...g.signal_ids, signalId],
      }
    }))
  }

  // Members split: assigned to a group or unassigned
  const assignedIds = new Set(groups.flatMap(g => g.member_ids))
  const unassigned  = members.filter(m => !assignedIds.has(m.id))

  return (
    <div className="p-8 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
          >
            Groups
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {groups.length} group{groups.length !== 1 ? 's' : ''} · {members.length} members
          </p>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 bg-[#171717] border border-white/[0.06] rounded-lg p-1">
          <button
            onClick={() => setActiveTab('members')}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
              activeTab === 'members'
                ? 'bg-[#ff6207]/15 text-[#ff8432] border border-[#ff6207]/25'
                : 'text-gray-500 hover:text-gray-300',
            )}
          >
            <Users size={12} />Members
          </button>
          <button
            onClick={() => setActiveTab('signals')}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all',
              activeTab === 'signals'
                ? 'bg-[#ff6207]/15 text-[#ff8432] border border-[#ff6207]/25'
                : 'text-gray-500 hover:text-gray-300',
            )}
          >
            <Radio size={12} />Signals
          </button>
        </div>

        <button
          onClick={() => { setShowCreate(v => !v); setCreateError('') }}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all',
            showCreate
              ? 'bg-[#1e1e1e] text-gray-400 border border-white/[0.06]'
              : 'bg-[#ff6207] text-white hover:bg-[#cc4e06] shadow-lg shadow-[#ff6207]/20',
          )}
        >
          <Plus size={14} className={clsx('transition-transform', showCreate && 'rotate-45')} />
          {showCreate ? 'Cancel' : 'New Group'}
        </button>
      </div>

      {/* Create group form */}
      {showCreate && (
        <div className="bg-[#171717] border border-[#ff6207]/20 rounded-2xl p-5 mb-6">
          <p className="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-4">
            New Group
          </p>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="text-[11px] text-gray-500 mb-1.5 block">Group name</label>
              <input
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && createGroup()}
                placeholder="e.g. BTC Whales, Premium…"
                className="w-full px-3 py-2 bg-[#1e1e1e] border border-white/[0.06] rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#ff6207]/40 transition-colors"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1.5 block">Color</label>
              <div className="flex gap-1.5">
                {GROUP_COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => setNewColor(c)}
                    className={clsx(
                      'w-7 h-7 rounded-lg transition-all',
                      newColor === c ? 'ring-2 ring-white/60 scale-110' : 'opacity-60 hover:opacity-100',
                    )}
                    style={{ background: c }}
                  />
                ))}
              </div>
            </div>
            <button
              onClick={createGroup}
              disabled={creating}
              className="px-5 py-2 bg-[#ff6207] text-white rounded-lg text-sm font-semibold hover:bg-[#cc4e06] transition-colors disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
          </div>
          {createError && <p className="text-xs text-red-400 mt-2">{createError}</p>}
        </div>
      )}

      {/* Empty state */}
      {groups.length === 0 && !showCreate && (
        <div className="flex flex-col items-center justify-center flex-1 text-gray-600">
          <Layers size={32} className="mb-3 opacity-30" />
          <p className="text-sm">No groups yet.</p>
          <p className="text-xs text-gray-700 mt-1">Create a group to start routing alerts.</p>
        </div>
      )}

      {/* ── MEMBERS TAB ── */}
      {activeTab === 'members' && groups.length > 0 && (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="flex gap-4 overflow-x-auto pb-4 flex-1">
            {/* Unassigned pool */}
            <GroupColumn
              id="unassigned"
              title="Unassigned"
              color="#6B7280"
              members={unassigned}
              onDelete={undefined}
            />

            {/* Group columns */}
            {groups.map(g => (
              <GroupColumn
                key={g.id}
                id={g.id}
                title={g.name}
                color={g.color}
                members={members.filter(m => g.member_ids.includes(m.id))}
                onDelete={() => deleteGroup(g.id)}
              />
            ))}
          </div>

          <DragOverlay dropAnimation={null}>
            {activeDrag && (
              <div className="bg-[#1e1e1e] border border-[#ff6207]/50 rounded-xl p-3 shadow-2xl shadow-black/60 rotate-1 w-52">
                <p className="text-sm font-medium text-white truncate">{activeDrag.name}</p>
                <p className="text-xs text-gray-500 truncate">{activeDrag.email}</p>
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      {/* ── SIGNALS TAB ── */}
      {activeTab === 'signals' && groups.length > 0 && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {groups.map(g => (
            <div
              key={g.id}
              className="bg-[#171717] border border-white/[0.06] rounded-2xl p-5 w-[260px] flex-shrink-0"
            >
              {/* Group header */}
              <div className="flex items-center gap-2.5 mb-4">
                <div
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ background: g.color }}
                />
                <p
                  className="font-semibold text-white text-sm"
                  style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
                >
                  {g.name}
                </p>
                <span className="ml-auto text-[10px] text-gray-600">
                  {g.signal_ids.length} signal{g.signal_ids.length !== 1 ? 's' : ''}
                </span>
              </div>

              {signals.length === 0 ? (
                <p className="text-xs text-gray-600">No signals configured.</p>
              ) : (
                <div className="space-y-1.5">
                  {signals.map(sig => {
                    const hasIt = g.signal_ids.includes(sig.id)
                    return (
                      <button
                        key={sig.id}
                        onClick={() => toggleSignal(g.id, sig.id, hasIt)}
                        className={clsx(
                          'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all text-left',
                          hasIt
                            ? 'bg-[#1e1e1e] border border-white/[0.08]'
                            : 'bg-transparent border border-white/[0.03] opacity-50 hover:opacity-70',
                        )}
                      >
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: sig.color }}
                        />
                        <span className="flex-1 text-white text-xs font-medium">{sig.name}</span>
                        <span className="text-[10px] font-mono text-gray-500">{sig.ticker}</span>
                        <div className={clsx(
                          'w-4 h-4 rounded flex items-center justify-center flex-shrink-0 transition-all',
                          hasIt ? 'bg-[#ff6207]' : 'bg-[#262626] border border-white/[0.08]',
                        )}>
                          {hasIt && <Check size={9} className="text-white" strokeWidth={3} />}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─── Group column (droppable) ─── */
function GroupColumn({
  id, title, color, members, onDelete,
}: {
  id: string
  title: string
  color: string
  members: Member[]
  onDelete?: () => void
}) {
  const { isOver, setNodeRef } = useDroppable({ id })

  return (
    <div
      ref={setNodeRef}
      className={clsx(
        'flex flex-col rounded-2xl border transition-all w-[220px] flex-shrink-0',
        isOver
          ? 'border-[#ff6207]/40 bg-[#ff6207]/5'
          : 'border-white/[0.06] bg-[#171717]',
      )}
      style={{ minHeight: 300 }}
    >
      {/* Column header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.05]">
        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
        <p
          className="text-sm font-semibold text-white flex-1 truncate"
          style={{ fontFamily: 'Switzer, Inter, sans-serif' }}
        >
          {title}
        </p>
        <span className="text-[10px] text-gray-600 flex-shrink-0">
          {members.length}
        </span>
        {onDelete && (
          <button
            onPointerDown={e => e.stopPropagation()}
            onClick={onDelete}
            className="ml-1 text-gray-700 hover:text-red-400 transition-colors flex-shrink-0"
          >
            <Trash2 size={11} />
          </button>
        )}
      </div>

      {/* Member cards */}
      <div className="flex-1 p-3 space-y-2 overflow-y-auto">
        {members.length === 0 && (
          <div className={clsx(
            'flex items-center justify-center h-16 rounded-lg border border-dashed text-[11px] transition-colors',
            isOver
              ? 'border-[#ff6207]/40 text-[#ff8432]'
              : 'border-white/[0.06] text-gray-700',
          )}>
            Drop here
          </div>
        )}
        {members.map(m => (
          <DraggableMember key={m.id} member={m} />
        ))}
      </div>
    </div>
  )
}

/* ─── Draggable member card ─── */
function DraggableMember({ member }: { member: Member }) {
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
        'bg-[#1e1e1e] border border-white/[0.05] rounded-xl p-3 select-none transition-all',
        isDragging ? 'opacity-30 scale-95' : 'opacity-100',
      )}
    >
      <div className="flex items-center gap-2">
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-gray-700 hover:text-gray-400 transition-colors flex-shrink-0"
        >
          <GripVertical size={12} />
        </div>
        <div className="w-6 h-6 rounded-lg bg-[#2a2a2a] flex items-center justify-center text-[10px] font-bold text-[#ff8432] flex-shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] font-medium text-white truncate leading-tight">{member.name}</p>
          <p className="text-[10px] text-gray-600 truncate">{member.email}</p>
        </div>
      </div>
    </div>
  )
}
