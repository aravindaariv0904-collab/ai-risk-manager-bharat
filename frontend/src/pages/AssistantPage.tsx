import { useState, useRef, useEffect } from 'react'
import { Bot, User, Send, Sparkles, MessageCircle } from 'lucide-react'
import { aiApi } from '../features/assistant/assistantService'
import { Button } from '../components/ui/Button'
import { Textarea } from '../components/ui/Textarea'
import { Alert } from '../components/ui/Alert'
import type { AssistantResult } from '../types'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
}

const SUGGESTIONS = [
  'Why was my last payment flagged?',
  'Show my high risk transactions.',
  'How much did I spend this week?',
  'What is my total spending?',
]

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'नमस्ते! I am your AI payment safety assistant. I can help you understand your transaction history, risk scores, and payment patterns.\n\nAsk me anything about your payments — I only answer from your actual data.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(text: string) {
    const query = text.trim()
    if (!query || loading) return

    setMessages((prev) => [...prev, { role: 'user', content: query, timestamp: new Date() }])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res: AssistantResult = await aiApi.query({ query })
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: res.answer,
        timestamp: new Date(),
      }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assistant temporarily unavailable')
    } finally {
      setLoading(false)
      textareaRef.current?.focus()
    }
  }

  function formatTime(date?: Date) {
    if (!date) return ''
    return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/10 shadow-inner">
            <Bot className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              AI Risk Assistant
              <Sparkles className="h-5 w-5 text-primary" />
            </h1>
            <p className="text-sm text-muted-foreground">
              Answers only from your actual payment data.
            </p>
          </div>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Constraint notice */}
      <div className="rounded-xl bg-primary/5 border border-primary/10 px-4 py-3 flex items-start gap-3">
        <MessageCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
        <p className="text-xs text-primary/80 font-medium">
          This assistant never invents transactions, risk scores, or payment data. It only answers based on your actual records.
        </p>
      </div>

      {/* Chat Container */}
      <div className="rounded-2xl border-0 shadow-md bg-white overflow-hidden flex flex-col" style={{ minHeight: '520px' }}>
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-gray-50/50 to-white" style={{ maxHeight: '420px' }}>
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex gap-3 animate-fade-in-up ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.role === 'assistant' && (
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/10 mt-1">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
              )}
              <div className={`max-w-[80%] ${m.role === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                <div className={m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'}>
                  <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
                </div>
                <p className="text-[10px] text-muted-foreground px-1">{formatTime(m.timestamp)}</p>
              </div>
              {m.role === 'user' && (
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-gray-100 mt-1">
                  <User className="h-4 w-4 text-gray-500" />
                </div>
              )}
            </div>
          ))}

          {/* Typing indicator */}
          {loading && (
            <div className="flex gap-3 justify-start animate-fade-in">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/10">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div className="chat-bubble-ai">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="h-2 w-2 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="h-2 w-2 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input Area */}
        <div className="border-t bg-white p-4 space-y-3">
          {/* Quick suggestions */}
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground hover:border-primary hover:text-primary hover:bg-primary/5 transition-all duration-150 disabled:opacity-40"
                onClick={() => sendMessage(s)}
                disabled={loading}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Input Row */}
          <div className="flex gap-2">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your payments, risk scores, or spending..."
              rows={2}
              className="resize-none rounded-xl border-border focus:border-primary text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage(input)
                }
              }}
            />
            <Button
              variant="default"
              size="icon"
              loading={loading}
              disabled={!input.trim()}
              onClick={() => sendMessage(input)}
              aria-label="Send message"
              className="h-full min-h-[72px] w-11 rounded-xl btn-primary-gradient flex-shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-xs text-center text-muted-foreground">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}