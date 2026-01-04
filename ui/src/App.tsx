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

interface LogEntry {
  timestamp: string
  level: string
  location: string
  message: string
  context: string
  raw: string
}

// ============================================
// Constants
// ============================================

const API_BASE = '/api/agentx'

const TOOL_CATEGORIES: Record<string, { category: string; color: string; icon: string; bgColor: string }> = {
  get_workflow: { category: 'Workflow', color: 'text-blue-700', icon: '📋', bgColor: 'bg-blue-100' },
  update_workflow: { category: 'Workflow', color: 'text-blue-700', icon: '📝', bgColor: 'bg-blue-100' },
  clear_workflow: { category: 'Workflow', color: 'text-blue-700', icon: '🗑️', bgColor: 'bg-blue-100' },
  add_node: { category: 'Node', color: 'text-green-700', icon: '➕', bgColor: 'bg-green-100' },
  remove_node: { category: 'Node', color: 'text-green-700', icon: '➖', bgColor: 'bg-green-100' },
  modify_node: { category: 'Node', color: 'text-green-700', icon: '✏️', bgColor: 'bg-green-100' },
  connect_nodes: { category: 'Connection', color: 'text-purple-700', icon: '🔗', bgColor: 'bg-purple-100' },
  disconnect_input: { category: 'Connection', color: 'text-purple-700', icon: '✂️', bgColor: 'bg-purple-100' },
  search_nodes: { category: 'Search', color: 'text-amber-700', icon: '🔍', bgColor: 'bg-amber-100' },
  get_node_info: { category: 'Search', color: 'text-amber-700', icon: 'ℹ️', bgColor: 'bg-amber-100' },
  list_node_categories: { category: 'Search', color: 'text-amber-700', icon: '📂', bgColor: 'bg-amber-100' },
  execute_workflow: { category: 'Execution', color: 'text-red-700', icon: '▶️', bgColor: 'bg-red-100' },
  get_execution_result: { category: 'Execution', color: 'text-red-700', icon: '📊', bgColor: 'bg-red-100' },
  interrupt_execution: { category: 'Execution', color: 'text-red-700', icon: '⏹️', bgColor: 'bg-red-100' },
  get_execution_logs: { category: 'Execution', color: 'text-red-700', icon: '📜', bgColor: 'bg-red-100' },
  monitor_execution: { category: 'Execution', color: 'text-red-700', icon: '👁️', bgColor: 'bg-red-100' },
  execute_and_monitor: { category: 'Execution', color: 'text-red-700', icon: '🎬', bgColor: 'bg-red-100' },
  validate_workflow: { category: 'Validation', color: 'text-teal-700', icon: '✅', bgColor: 'bg-teal-100' },
  analyze_workflow: { category: 'Validation', color: 'text-teal-700', icon: '📈', bgColor: 'bg-teal-100' },
  get_execution_images: { category: 'Image', color: 'text-pink-700', icon: '🖼️', bgColor: 'bg-pink-100' },
  get_latest_images: { category: 'Image', color: 'text-pink-700', icon: '📸', bgColor: 'bg-pink-100' },
  save_workflow_template: { category: 'Template', color: 'text-indigo-700', icon: '💾', bgColor: 'bg-indigo-100' },
  load_workflow_template: { category: 'Template', color: 'text-indigo-700', icon: '📥', bgColor: 'bg-indigo-100' },
  list_workflow_templates: { category: 'Template', color: 'text-indigo-700', icon: '📚', bgColor: 'bg-indigo-100' },
  delete_workflow_template: { category: 'Template', color: 'text-indigo-700', icon: '🗑️', bgColor: 'bg-indigo-100' },
  list_models: { category: 'System', color: 'text-slate-700', icon: '🤖', bgColor: 'bg-slate-100' },
  get_system_stats: { category: 'System', color: 'text-slate-700', icon: '📊', bgColor: 'bg-slate-100' },
  get_comfyui_info: { category: 'System', color: 'text-slate-700', icon: '⚙️', bgColor: 'bg-slate-100' },
  clear_queue: { category: 'System', color: 'text-slate-700', icon: '🧹', bgColor: 'bg-slate-100' },
}

const SYSTEM_PROMPT = `You are AgentX, an expert AI assistant for ComfyUI workflows.

## Available Tools
You have access to 26 ComfyUI tools in these categories:

### Workflow Tools
- get_workflow: Get current workflow
- update_workflow: Update/create entire workflow
- clear_workflow: Clear current workflow

### Node Tools
- add_node: Add a node to workflow
- remove_node: Remove a node
- modify_node: Modify node parameters
- connect_nodes: Connect two nodes
- disconnect_input: Disconnect an input

### Search Tools
- search_nodes: Search for nodes by keywords
- get_node_info: Get detailed node information
- list_node_categories: List all node categories

### Execution Tools
- execute_workflow: Execute the workflow
- get_execution_result: Get execution result
- interrupt_execution: Stop execution
- get_execution_logs: Get detailed execution logs (node timing, progress, errors)
- monitor_execution: Monitor execution in real-time via WebSocket
- execute_and_monitor: Execute and monitor in one call (recommended)

### Validation Tools
- validate_workflow: Validate workflow integrity
- analyze_workflow: Analyze workflow structure

### Image Tools
- get_execution_images: Get images from execution
- get_latest_images: Get recent images

### Template Tools
- save_workflow_template: Save as template
- load_workflow_template: Load template
- list_workflow_templates: List templates
- delete_workflow_template: Delete template

### System Tools
- list_models: List available models
- get_system_stats: Get system status
- get_comfyui_info: Get ComfyUI info
- clear_queue: Clear queue

## Rules
1. When asked to CREATE a workflow, use update_workflow immediately
2. After creating, use validate_workflow to check issues
3. Use analyze_workflow to provide suggestions
4. Always show what tools you're using`

// ============================================
// Utility Functions
// ============================================

function getToolMeta(toolName: string) {
  return TOOL_CATEGORIES[toolName] || { category: 'Other', color: 'text-gray-700', icon: '🔧', bgColor: 'bg-gray-100' }
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

// ============================================
// Components
// ============================================

function ToolCallCard({ tool, defaultExpanded = false }: { tool: ToolCall; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const meta = getToolMeta(tool.name)

  const statusConfig = {
    pending: { icon: '⏳', text: 'Pending', color: 'text-gray-500' },
    executing: { icon: '⚡', text: 'Executing...', color: 'text-blue-500 animate-pulse' },
    success: { icon: '✓', text: 'Success', color: 'text-green-600' },
    error: { icon: '✗', text: 'Error', color: 'text-red-600' },
  }

  const status = statusConfig[tool.status]

  return (
    <div className="my-2 border rounded-lg overflow-hidden bg-white shadow-sm">
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{meta.icon}</span>
          <span className="font-medium text-sm">{tool.name}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${meta.bgColor} ${meta.color}`}>
            {meta.category}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm ${status.color}`}>
            {status.icon} {status.text}
          </span>
          {tool.duration !== undefined && (
            <span className="text-xs text-gray-400">{(tool.duration / 1000).toFixed(2)}s</span>
          )}
          <span className="text-gray-400 text-sm transition-transform" style={{ transform: expanded ? 'rotate(180deg)' : 'none' }}>
            ▼
          </span>
        </div>
      </div>

      {expanded && (
        <div className="border-t p-3 space-y-3 bg-gray-50">
          <div>
            <div className="text-xs text-gray-500 mb-1 font-medium">Input:</div>
            <pre className="text-xs bg-white p-2 rounded border overflow-x-auto max-h-32 overflow-y-auto">
              {JSON.stringify(tool.arguments, null, 2)}
            </pre>
          </div>

          {tool.result !== undefined && (
            <div>
              <div className="text-xs text-gray-500 mb-1 font-medium">Output:</div>
              <pre className="text-xs bg-green-50 p-2 rounded border border-green-200 overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(tool.result, null, 2)}
              </pre>
            </div>
          )}

          {tool.error && (
            <div>
              <div className="text-xs text-gray-500 mb-1 font-medium">Error:</div>
              <pre className="text-xs bg-red-50 text-red-700 p-2 rounded border border-red-200">
                {tool.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({ className, children, ...props }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-800 text-sm" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            )
          },
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
          h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-bold mt-3 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-bold mt-2 mb-1">{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-600">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a href={href} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse border border-gray-300">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-gray-300 px-3 py-2 bg-gray-100 font-medium">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border border-gray-300 px-3 py-2">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function MessageBlock({ block, streamingText }: { block: Block; streamingText?: string }) {
  if (block.type === 'text') {
    const content = block.status === 'streaming' && streamingText ? streamingText : block.content
    return <MarkdownContent content={content} />
  }

  if (block.type === 'tool') {
    return <ToolCallCard tool={block.toolCall} />
  }

  return null
}

function MessageItem({ message, streamingText }: { message: Message; streamingText?: string }) {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-3xl px-4 py-3 rounded-2xl bg-blue-600 text-white">
          {message.content}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex justify-start">
        <div className="max-w-3xl px-4 py-3 rounded-2xl bg-red-50 border border-red-200 text-red-700">
          {message.content}
        </div>
      </div>
    )
  }

  // Assistant message with blocks
  return (
    <div className="flex justify-start">
      <div className="max-w-3xl w-full">
        <div className="bg-white shadow-sm border rounded-2xl px-4 py-3">
          {message.blocks?.map((block, idx) => (
            <MessageBlock
              key={block.id || idx}
              block={block}
              streamingText={block.type === 'text' && block.status === 'streaming' ? streamingText : undefined}
            />
          ))}

          {/* Simple text content fallback */}
          {!message.blocks?.length && message.content && (
            <MarkdownContent content={message.content} />
          )}

          {/* Loading indicator for streaming */}
          {message.status === 'streaming' && !message.blocks?.length && (
            <div className="flex items-center gap-2 text-gray-400">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusIndicator({ status }: { status: 'idle' | 'connecting' | 'thinking' | 'responding' | 'calling_tool' | 'error' }) {
  const config = {
    idle: { text: 'Ready', color: 'bg-green-500' },
    connecting: { text: 'Connecting...', color: 'bg-yellow-500 animate-pulse' },
    thinking: { text: 'Thinking...', color: 'bg-blue-500 animate-pulse' },
    responding: { text: 'Responding...', color: 'bg-blue-500 animate-pulse' },
    calling_tool: { text: 'Calling tool...', color: 'bg-purple-500 animate-pulse' },
    error: { text: 'Error', color: 'bg-red-500' },
  }

  const { text, color } = config[status]

  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <div className={`w-2 h-2 rounded-full ${color}`} />
      <span>{text}</span>
    </div>
  )
}

// ============================================
// Main App Component
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

  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions()
  }, [])

  // Clean up WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`)
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (e) {
      console.error('Failed to fetch sessions:', e)
    }
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
      setCurrentSession(session.session_id)
      setMessages([])
      connectWebSocket(session.session_id)
    } catch (e) {
      console.error('Failed to create session:', e)
    }
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
      console.error('Failed to fetch messages:', e)
      setMessages([])
    }
  }

  const connectWebSocket = useCallback((sessionId: string) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${API_BASE}/sessions/${sessionId}/stream`

    setStatus('connecting')
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket connected')
      setStatus('idle')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setStatus('error')
    }

    ws.onclose = () => {
      console.log('WebSocket closed')
      if (status !== 'error') {
        setStatus('idle')
      }
    }

    wsRef.current = ws
  }, [status])

  const handleWebSocketMessage = useCallback((data: any) => {
    const { type } = data

    switch (type) {
      case 'state':
        // Backend sends lowercase state values
        const state = data.data?.state?.toLowerCase()
        if (state === 'thinking') setStatus('thinking')
        else if (state === 'responding') setStatus('responding')
        else if (state === 'calling_tool') setStatus('calling_tool')
        else if (state === 'done' || state === 'idle') setStatus('idle')
        else if (state === 'error') setStatus('error')
        break

      case 'stream':
        // Streaming text delta
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
                blocks: blocks.map((b, i) =>
                  i === blocks.length - 1 && b.type === 'text'
                    ? { ...b, content: b.content + data.data }
                    : b
                )
              }
            }

            return {
              ...msg,
              blocks: [...blocks, {
                id: generateId(),
                type: 'text',
                content: data.data,
                status: 'streaming'
              }]
            }
          })
        })
        break

      case 'tool_use':
        // Tool call started
        const toolUse = data.data
        setMessages(prev => {
          const msgId = currentAssistantMsgRef.current
          if (!msgId) return prev

          return prev.map(msg => {
            if (msg.id !== msgId) return msg

            // Complete any streaming text block
            const blocks = (msg.blocks || []).map(b =>
              b.type === 'text' && b.status === 'streaming'
                ? { ...b, status: 'completed' as const }
                : b
            )

            return {
              ...msg,
              blocks: [...blocks, {
                id: generateId(),
                type: 'tool',
                toolCall: {
                  id: toolUse.id,
                  name: toolUse.name,
                  arguments: toolUse.input,
                  status: 'executing',
                  startTime: Date.now()
                }
              }]
            }
          })
        })
        setStreamingText('')
        break

      case 'tool_result':
        // Tool execution completed
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
                  const duration = b.toolCall.startTime ? Date.now() - b.toolCall.startTime : undefined
                  return {
                    ...b,
                    toolCall: {
                      ...b.toolCall,
                      result: toolResult.content,
                      status: toolResult.content?.error ? 'error' : 'success',
                      duration
                    }
                  }
                }
                return b
              })
            }
          })
        })
        break

      case 'message':
        // Final message content
        const messageContent = data.data?.content
        if (messageContent) {
          setMessages(prev => {
            const msgId = currentAssistantMsgRef.current
            if (!msgId) return prev

            return prev.map(msg => {
              if (msg.id !== msgId) return msg

              // Complete all blocks and add final text if different
              const blocks = (msg.blocks || []).map(b =>
                b.type === 'text' && b.status === 'streaming'
                  ? { ...b, status: 'completed' as const }
                  : b
              )

              return {
                ...msg,
                content: messageContent,
                status: 'completed',
                blocks
              }
            })
          })
        }
        break

      case 'turn':
        // Turn completed
        currentAssistantMsgRef.current = null
        setStreamingText('')
        setStatus('idle')
        break

      case 'error':
        setMessages(prev => [...prev, {
          id: generateId(),
          role: 'error',
          content: data.data?.message || 'An error occurred',
        }])
        setStatus('error')
        break
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

    // Create placeholder for assistant response
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

    // Send via WebSocket if connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'message',
        content: input,
        system: SYSTEM_PROMPT
      }))
    } else {
      // Fallback to HTTP
      try {
        const res = await fetch(`${API_BASE}/sessions/${currentSession}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: input,
            system: SYSTEM_PROMPT
          })
        })
        const data = await res.json()

        if (data.error) {
          setMessages(prev => prev.map(msg =>
            msg.id === assistantMsgId
              ? { ...msg, role: 'error', content: data.error, status: 'completed' }
              : msg
          ))
        } else {
          const blocks: Block[] = []

          if (data.executed_tools) {
            for (const tool of data.executed_tools) {
              blocks.push({
                id: generateId(),
                type: 'tool',
                toolCall: {
                  id: tool.id || generateId(),
                  name: tool.name,
                  arguments: tool.arguments,
                  result: tool.result,
                  status: tool.result?.error ? 'error' : 'success'
                }
              })
            }
          }

          if (data.content) {
            blocks.push({
              id: generateId(),
              type: 'text',
              content: data.content,
              status: 'completed'
            })
          }

          setMessages(prev => prev.map(msg =>
            msg.id === assistantMsgId
              ? { ...msg, content: data.content, blocks, status: 'completed' }
              : msg
          ))
        }
      } catch (e) {
        console.error('Failed to send message:', e)
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, role: 'error', content: 'Failed to send message', status: 'completed' }
            : msg
        ))
      } finally {
        setStatus('idle')
        currentAssistantMsgRef.current = null
      }
    }
  }, [input, currentSession, status])

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold">ComfyUI AgentX</h1>
          <p className="text-xs text-gray-400 mt-1">AI Workflow Assistant</p>
        </div>

        <button
          onClick={createSession}
          className="m-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition font-medium"
        >
          + New Chat
        </button>

        <div className="flex-1 overflow-y-auto">
          {sessions.map(session => (
            <div
              key={session.session_id}
              onClick={() => selectSession(session.session_id)}
              className={`p-3 cursor-pointer hover:bg-gray-800 transition ${
                currentSession === session.session_id ? 'bg-gray-800 border-l-2 border-blue-500' : ''
              }`}
            >
              <div className="font-medium truncate">{session.title || 'Untitled'}</div>
              <div className="text-xs text-gray-400">
                {new Date(session.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>

        {/* Status indicator at bottom */}
        <div className="p-4 border-t border-gray-700">
          <StatusIndicator status={status} />
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {currentSession ? (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center text-gray-500 mt-8">
                  <p className="text-lg font-medium">Start a conversation</p>
                  <p className="text-sm mt-2">Ask about ComfyUI nodes, workflows, or debugging</p>
                  <div className="mt-6 grid grid-cols-2 gap-2 max-w-md mx-auto">
                    {[
                      'Create a text-to-image workflow',
                      'List available models',
                      'Analyze my current workflow',
                      'Search for upscale nodes'
                    ].map(prompt => (
                      <button
                        key={prompt}
                        onClick={() => setInput(prompt)}
                        className="p-3 text-left text-sm bg-white rounded-lg shadow-sm hover:shadow-md transition border"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map(msg => (
                <MessageItem
                  key={msg.id}
                  message={msg}
                  streamingText={msg.id === currentAssistantMsgRef.current ? streamingText : undefined}
                />
              ))}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t bg-white p-4">
              <div className="flex gap-2 max-w-4xl mx-auto">
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  className="flex-1 px-4 py-2 border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  rows={1}
                  disabled={status !== 'idle'}
                />
                <button
                  onClick={sendMessage}
                  disabled={status !== 'idle' || !input.trim()}
                  className="px-6 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
                >
                  Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center max-w-md">
              <h2 className="text-2xl font-bold mb-4">Welcome to ComfyUI AgentX</h2>
              <p className="mb-6">Your AI-powered workflow assistant with 26 specialized tools</p>
              <button
                onClick={createSession}
                className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition font-medium"
              >
                Start New Chat
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
