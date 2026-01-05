import React, { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ============================================ 
// Types
// ============================================ 

interface ToolCall {
  id: string
  name: string
  arguments: Record<string, any>
  result?: any
  error?: string
  status: 'pending' | 'executing' | 'success' | 'error'
  duration?: number
  startTime?: number
}

interface TextBlock {
  id: string
  type: 'text'
  content: string
  status: 'streaming' | 'completed'
}

interface ToolBlock {
  id: string
  type: 'tool'
  toolCall: ToolCall
}

type Block = TextBlock | ToolBlock

interface Message {
  id: string
  role: 'user' | 'assistant' | 'error'
  content?: string
  blocks?: Block[]
  timestamp?: string
  status?: 'pending' | 'streaming' | 'completed' | 'error'
}

interface Session {
  session_id: string
  title: string
  created_at: string
  state: string
}

// ============================================ 
// Constants
// ============================================ 

const API_BASE = '/api/agentx'

const SYSTEM_PROMPT = `You are AgentX, an expert AI assistant for ComfyUI workflows.

## Available Tools
You have access to 26 ComfyUI tools.

## Rules
1. When asked to CREATE a workflow, use update_workflow immediately
2. After creating, use validate_workflow to check issues
3. Use analyze_workflow to provide suggestions
4. Always show what tools you're using`

// ============================================ 
// Utility Functions
// ============================================ 

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

function cleanContent(content: string): string {
  if (!content) return ''
  let cleaned = content.replace(/<think>[\s\S]*?<\/think>/gi, '')
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n')
  return cleaned.trim()
}

// ============================================ 
// Components
// ============================================ 

const UserIcon = () => (
  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0">
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  </div>
)

const AssistantIcon = () => (
  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white flex-shrink-0 shadow-sm">
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  </div>
)

function ToolCallCard({ tool }: { tool: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  
  const statusColors = {
    pending: 'bg-gray-50 text-gray-400 border-gray-100',
    executing: 'bg-blue-50/50 text-blue-500 border-blue-100 animate-pulse',
    success: 'bg-emerald-50/50 text-emerald-600 border-emerald-100',
    error: 'bg-rose-50/50 text-rose-600 border-rose-100',
  }
  
  const statusIcons = {
    pending: '⌛',
    executing: '⚡',
    success: '✨',
    error: '❌',
  }

  return (
    <div className={`my-3 text-xs border rounded-xl overflow-hidden transition-all duration-200 ${statusColors[tool.status]}`}>
      <div 
        className="flex items-center justify-between px-4 py-2.5 cursor-pointer hover:bg-black/5"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 font-medium">
          <span className="text-sm">{statusIcons[tool.status]}</span>
          <span className="opacity-70 font-semibold tracking-wider text-[10px] uppercase">Action</span>
          <span className="font-mono text-[11px] px-1.5 py-0.5 bg-black/5 rounded">{tool.name}</span>
        </div>
        <div className="flex items-center gap-3">
          {tool.duration && <span className="opacity-40 font-mono">{(tool.duration / 1000).toFixed(2)}s</span>}
          <svg className={`w-3 h-3 transition-transform duration-200 opacity-40 ${expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {expanded && (
        <div className="p-4 border-t border-inherit bg-white/40 backdrop-blur-sm">
          <div className="space-y-3">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-1 h-3 bg-blue-400 rounded-full" />
                <span className="font-bold opacity-60 text-[10px] uppercase tracking-wider">Input Parameters</span>
              </div>
              <pre className="overflow-x-auto p-3 rounded-lg bg-gray-900 text-gray-300 font-mono text-[11px] leading-relaxed border border-gray-800 shadow-inner">
                {JSON.stringify(tool.arguments, null, 2)}
              </pre>
            </div>
            {tool.result && (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="w-1 h-3 bg-emerald-400 rounded-full" />
                  <span className="font-bold opacity-60 text-[10px] uppercase tracking-wider">Result Output</span>
                </div>
                <pre className="overflow-x-auto p-3 rounded-lg bg-gray-900 text-gray-300 font-mono text-[11px] leading-relaxed border border-gray-800 shadow-inner max-h-80">
                  {JSON.stringify(tool.result, null, 2)}
                </pre>
              </div>
            )}
            {tool.error && (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="w-1 h-3 bg-rose-400 rounded-full" />
                  <span className="font-bold text-rose-500 text-[10px] uppercase tracking-wider">Execution Error</span>
                </div>
                <pre className="overflow-x-auto p-3 rounded-lg bg-rose-900/20 text-rose-200 font-mono text-[11px] border border-rose-500/20 shadow-inner">
                  {tool.error}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MarkdownContent({ content }: { content: string }) {
  const cleaned = cleanContent(content)
  
  return (
    <div className="prose prose-sm max-w-none text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({ className, children, ...props }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800 text-indigo-600 dark:text-indigo-400 font-mono text-[0.9em] border border-black/5" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <div className="relative group my-4 rounded-xl overflow-hidden border border-gray-800 shadow-xl">
                <div className="bg-gray-800/50 px-4 py-2 text-[10px] text-gray-400 border-b border-gray-800 flex justify-between items-center">
                  <span className="font-mono uppercase tracking-widest">{className?.replace('language-', '') || 'code'}</span>
                </div>
                <pre className="bg-gray-900 text-gray-300 p-5 overflow-x-auto font-mono text-[13px] leading-relaxed scrollbar-thin scrollbar-thumb-gray-700">
                  <code className={className} {...props}>
                    {children}
                  </code>
                </pre>
              </div>
            )
          },
          p: ({ children }) => <p className="mb-4 last:mb-0 text-[14.5px] leading-7">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-6 mb-4 space-y-2 text-[14.5px]">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-6 mb-4 space-y-2 text-[14.5px]">{children}</ol>,
          h1: ({ children }) => <h3 className="text-xl font-bold mt-8 mb-4 text-gray-900 dark:text-white border-b border-black/5 pb-2">{children}</h3>,
          h2: ({ children }) => <h4 className="text-lg font-bold mt-6 mb-3 text-gray-800 dark:text-gray-100">{children}</h4>,
          h3: ({ children }) => <h5 className="text-base font-bold mt-5 mb-2 text-gray-700 dark:text-gray-200 uppercase tracking-wide">{children}</h5>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-indigo-400 pl-5 italic text-gray-600 dark:text-gray-400 my-6 bg-indigo-50/30 dark:bg-indigo-900/10 py-3 rounded-r-xl">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a href={href} className="text-blue-600 dark:text-blue-400 hover:text-blue-500 font-medium underline underline-offset-4 decoration-blue-500/30 transition-colors" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="overflow-hidden my-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800 text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 bg-gray-50/80 dark:bg-gray-800/50 font-semibold text-left text-gray-900 dark:text-gray-100">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 border-t border-gray-100 dark:border-gray-800/50 bg-white/50 dark:bg-transparent">{children}</td>
          ),
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  )
}

function MessageItem({ message, streamingText }: { message: Message; streamingText?: string }) {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'

  return (
    <div className={`flex gap-4 mb-8 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {isUser ? <UserIcon /> : <AssistantIcon />}
      
      <div className={`max-w-[80%] min-w-0 flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-5 py-3.5 rounded-2xl shadow-sm transition-all duration-300 ${ 
          isUser 
            ? 'bg-gradient-to-br from-indigo-600 to-blue-600 text-white rounded-tr-none' 
            : isError
              ? 'bg-rose-50 border border-rose-100 text-rose-700 rounded-tl-none'
              : 'bg-white dark:bg-gray-800 border dark:border-gray-700/50 rounded-tl-none shadow-[0_2px_15px_-3px_rgba(0,0,0,0.07)]'
        }`}>
          {isUser ? (
            <div className="whitespace-pre-wrap text-[15px] leading-relaxed">{message.content}</div>
          ) : isError ? (
            <div>
              <div className="font-bold text-xs uppercase tracking-widest mb-1 opacity-70">Error</div>
              <div className="text-[14px]">{message.content}</div>
            </div>
          ) : (
            <>
              {message.blocks?.map((block, idx) => {
                if (block.type === 'tool') {
                  return <ToolCallCard key={block.id || idx} tool={block.toolCall} />
                }
                if (block.type === 'text') {
                  const text = block.status === 'streaming' && streamingText ? streamingText : block.content
                  return <MarkdownContent key={block.id || idx} content={text} />
                }
                return null
              })}

              {!message.blocks?.length && message.content && (
                <MarkdownContent content={message.content} />
              )}

              {message.status === 'streaming' && !message.blocks?.length && (
                <div className="flex items-center gap-1.5 py-3 px-2">
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
                </div>
              )}
            </>
          )}
        </div>
        <div className="mt-1.5 px-1 flex items-center gap-2">
          <span className="text-[10px] text-gray-400 font-medium uppercase tracking-tighter">
            {isUser ? 'You' : 'AgentX'}
          </span>
          {message.timestamp && (
            <span className="text-[10px] text-gray-300">
              {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function Sidebar({ sessions, currentSession, onCreateSession, onSelectSession }: any) {
  return (
    <div className="w-72 bg-[#0f111a] text-gray-400 flex flex-col border-r border-gray-800/50 flex-shrink-0">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-blue-500 to-cyan-400 p-[1px] shadow-lg shadow-indigo-500/20">
            <div className="w-full h-full rounded-[11px] bg-[#0f111a] flex items-center justify-center text-white">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
          <div>
            <h1 className="text-white font-bold text-base tracking-tight leading-none">AgentX</h1>
            <span className="text-[10px] text-indigo-400 font-bold uppercase tracking-widest">Copilot</span>
          </div>
        </div>
        
        <button
          onClick={onCreateSession}
          className="w-full py-3 px-4 bg-white/5 hover:bg-white/10 text-white rounded-xl transition-all duration-200 border border-white/5 font-semibold flex items-center justify-center gap-2.5 group active:scale-[0.98]"
        >
          <svg className="w-4 h-4 group-hover:rotate-90 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-1.5 scrollbar-thin scrollbar-thumb-gray-800/50">
        <div className="px-3 py-2 text-[10px] font-bold text-gray-600 uppercase tracking-[0.2em] mb-2">Recent Threads</div>
        {sessions.map((session: Session) => (
          <div
            key={session.session_id}
            onClick={() => onSelectSession(session.session_id)}
            className={`group p-3 rounded-xl cursor-pointer transition-all duration-200 border ${ 
              currentSession === session.session_id 
                ? 'bg-indigo-600/10 text-white border-indigo-500/30 shadow-[0_0_20px_-5px_rgba(99,102,241,0.2)]' 
                : 'hover:bg-white/5 text-gray-500 hover:text-gray-300 border-transparent'
            }`}
          >
            <div className="font-semibold text-[13px] truncate leading-tight mb-1">
              {session.title || 'Untitled Conversation'}
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${currentSession === session.session_id ? 'bg-indigo-400' : 'bg-gray-700'}`} />
              <span className="text-[10px] opacity-60">
                {new Date(session.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================ 
// Main App
// ============================================ 

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<'idle' | 'connecting' | 'thinking' | 'responding' | 'calling_tool' | 'error'>('idle')
  const [streamingText, setStreamingText] = useState('')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const currentAssistantMsgRef = useRef<string | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText, status])

  useEffect(() => {
    fetchSessions()
    return () => wsRef.current?.close()
  }, [])

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`)
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (e) { console.error(e) }
  }

  const createSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat' })
      })
      const session = await res.json()
      setSessions(prev => [session, ...prev])
      selectSession(session.session_id)
    } catch (e) { console.error(e) }
  }

  const selectSession = async (sessionId: string) => {
    setCurrentSession(sessionId)
    wsRef.current?.close()

    try {
      const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`)
      const data = await res.json()
      if (data.messages) {
        setMessages(data.messages.map((m: any) => ({
          id: m.message_id || generateId(),
          role: m.role.toLowerCase(),
          content: m.content,
          blocks: m.tool_calls?.map((tc: any) => ({
            id: tc.id || generateId(),
            type: 'tool' as const,
            toolCall: {
              id: tc.id,
              name: tc.name,
              arguments: tc.arguments || tc.input,
              result: tc.result,
              error: tc.error,
              status: tc.error ? 'error' : tc.result ? 'success' : 'pending'
            }
          }))
        })))
      }
      connectWebSocket(sessionId)
    } catch (e) {
      console.error(e)
      setMessages([])
    }
  }

  const connectWebSocket = useCallback((sessionId: string) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${API_BASE}/sessions/${sessionId}/stream`

    setStatus('connecting')
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => { setStatus('idle') }
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      } catch (e) { console.error(e) }
    }
    ws.onerror = () => setStatus('error')
    ws.onclose = () => { if (status !== 'error') setStatus('idle') }
    wsRef.current = ws
  }, [status])

  const handleWebSocketMessage = useCallback((data: any) => {
    const { type } = data

    if (type === 'state') {
      const state = data.data?.state?.toLowerCase()
      if (['thinking', 'responding', 'calling_tool'].includes(state)) setStatus(state)
      else if (state === 'done' || state === 'idle') setStatus('idle')
      else if (state === 'error') setStatus('error')
      return
    }

    if (type === 'stream') {
      setStreamingText(prev => prev + data.data)
      setMessages(prev => {
        const msgId = currentAssistantMsgRef.current
        if (!msgId) return prev
        return prev.map(msg => {
          if (msg.id !== msgId) return msg
          const blocks = msg.blocks || []
          const lastBlock = blocks[blocks.length - 1]
          if (lastBlock?.type === 'text' && lastBlock.status === 'streaming') {
            return {
              ...msg,
              blocks: blocks.map((b, i) => i === blocks.length - 1 ? { ...b, content: b.content + data.data } : b)
            }
          }
          return {
            ...msg,
            blocks: [...blocks, { id: generateId(), type: 'text', content: data.data, status: 'streaming' }]
          }
        })
      })
      return
    }

    if (type === 'tool_use') {
      const toolUse = data.data
      setMessages(prev => {
        const msgId = currentAssistantMsgRef.current
        if (!msgId) return prev
        return prev.map(msg => {
          if (msg.id !== msgId) return msg
          const blocks = (msg.blocks || []).map(b => b.type === 'text' && b.status === 'streaming' ? { ...b, status: 'completed' as const } : b)
          return {
            ...msg,
            blocks: [...blocks, {
              id: generateId(),
              type: 'tool',
              toolCall: { id: toolUse.id, name: toolUse.name, arguments: toolUse.input, status: 'executing', startTime: Date.now() }
            }]
          }
        })
      })
      setStreamingText('')
      return
    }

    if (type === 'tool_result') {
      const toolResult = data.data
      setMessages(prev => {
        const msgId = currentAssistantMsgRef.current
        if (!msgId) return prev
        return prev.map(msg => {
          if (msg.id !== msgId) return msg
          return {
            ...msg,
            blocks: msg.blocks?.map(b => {
              if (b.type === 'tool' && b.toolCall.id === toolResult.tool_use_id) {
                return {
                  ...b,
                  toolCall: {
                    ...b.toolCall,
                    result: toolResult.content,
                    status: toolResult.content?.error ? 'error' : 'success',
                    duration: b.toolCall.startTime ? Date.now() - b.toolCall.startTime : undefined
                  }
                }
              }
              return b
            })
          }
        })
      })
      return
    }

    if (type === 'turn') {
      currentAssistantMsgRef.current = null
      setStreamingText('')
      setStatus('idle')
    }
  }, [])

  const sendMessage = useCallback(async () => {
    if (!input.trim() || !currentSession || status !== 'idle') return

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    const assistantMsgId = generateId()
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      blocks: [],
      status: 'streaming'
    }

    currentAssistantMsgRef.current = assistantMsgId
    setMessages(prev => [...prev, userMessage, assistantMessage])
    setInput('')
    setStreamingText('')
    setStatus('thinking')

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'message',
        content: input,
        system: SYSTEM_PROMPT
      }))
    }
  }, [input, currentSession, status])

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-screen bg-gray-50/50 text-gray-900 font-sans selection:bg-indigo-100">
      <Sidebar 
        sessions={sessions} 
        currentSession={currentSession}
        onCreateSession={createSession}
        onSelectSession={selectSession}
      />

      <div className="flex-1 flex flex-col min-w-0 bg-white/40 backdrop-blur-3xl relative overflow-hidden">
        {/* Decorative background blob */}
        <div className="absolute -top-[10%] -right-[5%] w-[40%] h-[40%] bg-indigo-50 rounded-full blur-[120px] -z-10 opacity-60" />
        <div className="absolute -bottom-[5%] -left-[5%] w-[30%] h-[30%] bg-blue-50 rounded-full blur-[100px] -z-10 opacity-60" />

        {!currentSession ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="w-24 h-24 bg-gradient-to-tr from-indigo-600 to-blue-500 rounded-[2rem] flex items-center justify-center text-4xl mb-8 shadow-2xl shadow-indigo-500/20 rotate-3 hover:rotate-0 transition-transform duration-500">
              ⚡
            </div>
            <h2 className="text-4xl font-extrabold text-gray-900 mb-4 tracking-tight">AgentX Assistant</h2>
            <p className="text-gray-500 max-w-sm mb-10 text-lg leading-relaxed">
              Your AI partner for creating, analyzing and debugging ComfyUI workflows.
            </p>
            <button
              onClick={createSession}
              className="px-10 py-4 bg-[#0f111a] hover:bg-black text-white rounded-2xl font-bold shadow-xl shadow-black/10 transition-all hover:scale-[1.02] active:scale-95 flex items-center gap-3"
            >
              Start a New Session
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </button>
          </div>
        ) : (
          <>
            <header className="bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4 flex items-center justify-between z-10 sticky top-0">
              <div className="flex items-center gap-4">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)] animate-pulse" />
                <h2 className="font-bold text-gray-800 tracking-tight">
                  {sessions.find(s => s.session_id === currentSession)?.title || 'Current Chat'}
                </h2>
              </div>
              <div className="flex items-center gap-3">
                <div className="px-3 py-1 bg-indigo-50 rounded-full text-[10px] font-bold text-indigo-600 uppercase tracking-widest border border-indigo-100/50">
                  {status.replace('_', ' ')}
                </div>
              </div>
            </header>

            <div className="flex-1 overflow-y-auto p-6 md:p-10 lg:px-32 space-y-2 scroll-smooth">
              {messages.map(msg => (
                <MessageItem
                  key={msg.id}
                  message={msg}
                  streamingText={msg.id === currentAssistantMsgRef.current ? streamingText : undefined}
                />
              ))}
              <div ref={messagesEndRef} className="h-8" />
            </div>

            <div className="px-6 pb-8 pt-4">
              <div className="max-w-4xl mx-auto">
                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-blue-500 rounded-2xl blur opacity-0 group-focus-within:opacity-15 transition duration-500" />
                  <textarea
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="Describe your workflow or ask a question..."
                    className="relative w-full pl-6 pr-20 py-5 rounded-2xl border border-gray-200 bg-white focus:ring-0 focus:border-indigo-400 transition-all resize-none shadow-xl shadow-black/5 text-[15px] leading-relaxed"
                    rows={1}
                    style={{ minHeight: '70px', maxHeight: '250px' }}
                    disabled={status !== 'idle' && status !== 'error'}
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!input.trim() || (status !== 'idle' && status !== 'error')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-12 h-12 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-20 disabled:grayscale transition-all shadow-lg shadow-indigo-600/30 flex items-center justify-center group/btn active:scale-90"
                  >
                    <svg className="w-5 h-5 group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  </button>
                </div>
                <div className="flex justify-between items-center mt-3 px-2">
                  <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-[0.15em] flex items-center gap-2">
                    <kbd className="px-1.5 py-0.5 bg-gray-100 rounded border border-gray-200 text-gray-500 font-sans shadow-sm">Enter</kbd>
                    to Send
                  </span>
                  <div className="flex gap-4">
                    <span className="text-[10px] text-gray-400 font-bold hover:text-indigo-500 cursor-pointer transition-colors uppercase tracking-wider">Help</span>
                    <span className="text-[10px] text-gray-400 font-bold hover:text-indigo-500 cursor-pointer transition-colors uppercase tracking-wider">Settings</span>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
