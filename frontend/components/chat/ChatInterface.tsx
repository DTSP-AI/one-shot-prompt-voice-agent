'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import {
  Send,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Bot,
  User,
  Loader2,
  Copy
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useApi } from '@/lib/api-provider'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
}

interface AgentInvokeResponse {
  success: boolean
  agent_response?: string
  error?: string
}

interface Agent {
  id: string
  config: {
    payload: {
      name: string
      shortDescription: string
      avatar?: string
      voice?: {
        elevenlabsVoiceId?: string
      }
    }
  }
}

interface ChatInterfaceProps {
  agent: Agent | null
  conversationId?: string
}

export function ChatInterface({ agent, conversationId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const api = useApi()
  const sessionId = useRef(conversationId || `${agent?.id}-${Date.now()}`)

  useEffect(() => {
    if (agent && !conversationId) {
      const welcome: Message = {
        id: 'welcome',
        content: `Hello! I'm ${agent.config.payload.name}. ${agent.config.payload.shortDescription}`,
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages([welcome])
    }
  }, [agent, conversationId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!inputMessage.trim() || !agent || isLoading) return

    const userMsg: Message = {
      id: Date.now().toString(),
      content: inputMessage.trim(),
      role: 'user',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMsg])
    setInputMessage('')
    setIsLoading(true)

    try {
      const data = await api.post<AgentInvokeResponse>('/api/v1/agent/invoke', {
        user_input: userMsg.content,
        session_id: sessionId.current,
        tenant_id: 'default',
        voice_id: agent.config.payload.voice?.elevenlabsVoiceId,
        tts_enabled: false,
        model: 'gpt-4',
        agent_id: agent.id,
        traits: {
          name: agent.config.payload.name,
          shortDescription: agent.config.payload.shortDescription,
          identity: "I am an AI assistant",
          mission: "To help users with their questions and tasks",
          interactionStyle: "Friendly and helpful",
          creativity: 75,
          empathy: 80,
          assertiveness: 60,
          verbosity: 50,
          formality: 40,
          confidence: 70,
          humor: 35,
          technicality: 65,
          safety: 90
        }
      })

      if (data?.success && data?.agent_response) {
        const assistantMsg: Message = {
          id: (Date.now() + 1).toString(),
          content: data.agent_response,
          role: 'assistant',
          timestamp: new Date()
        }
        setMessages(prev => [...prev, assistantMsg])
      } else {
        throw new Error(data?.error || 'Agent failed to respond')
      }
    } catch (err) {
      console.error(err)
      toast.error('Failed to get agent response')
      const errorMsg: Message = {
        id: 'error',
        content: '⚠️ Error: Agent unavailable',
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const toggleListen = () => {
    setIsListening(l => !l)
    toast.info(isListening ? 'Stopped listening' : 'Started listening')
  }

  const toggleSpeak = () => {
    setIsSpeaking(s => !s)
    toast.info(isSpeaking ? 'Stopped speaking' : 'Started speaking')
  }

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content)
    toast.success('Copied to clipboard')
  }

  if (!agent) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <Bot className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">Select an Agent</h3>
          <p className="text-muted-foreground">
            Choose an agent from the sidebar to start chatting
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b bg-background/95 backdrop-blur">
        <Avatar className="h-10 w-10">
          <AvatarImage
            src={
              agent.config.payload.avatar ||
              (agent.config.payload.name.toLowerCase().includes('rick')
                ? '/assets/avatars/rick_avatar.png'
                : undefined)
            }
          />
          <AvatarFallback>
            <Bot className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <h2 className="font-semibold">{agent.config.payload.name}</h2>
          <p className="text-sm text-muted-foreground">
            {agent.config.payload.shortDescription}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={isSpeaking ? 'default' : 'outline'}
            onClick={toggleSpeak}
          >
            {isSpeaking ? (
              <VolumeX className="h-4 w-4" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}
          </Button>
          <Badge variant="secondary">Online</Badge>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(m => (
          <div
            key={m.id}
            className={cn(
              'flex gap-3 max-w-4xl',
              m.role === 'user' ? 'ml-auto flex-row-reverse' : ''
            )}
          >
            <Avatar className="h-8 w-8 flex-shrink-0">
              <AvatarFallback>
                {m.role === 'user' ? (
                  <User className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </AvatarFallback>
            </Avatar>
            <Card
              className={cn(
                'flex-1',
                m.role === 'user' ? 'bg-primary text-primary-foreground' : ''
              )}
            >
              <CardContent className="p-3">
                <div>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/50">
                    <span className="text-xs opacity-70">
                      {m.timestamp.toLocaleTimeString()}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => copyMessage(m.content)}
                      className="h-6 w-6 p-0"
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4 bg-background/95 backdrop-blur">
        <div className="flex items-center gap-2 max-w-4xl mx-auto">
          <Button
            size="sm"
            variant={isListening ? 'default' : 'outline'}
            onClick={toggleListen}
          >
            {isListening ? (
              <MicOff className="h-4 w-4" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </Button>
          <div className="flex-1 relative">
            <Input
              value={inputMessage}
              onChange={e => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Message ${agent.config.payload.name}...`}
              disabled={isLoading}
              className="pr-12"
            />
            <Button
              size="sm"
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading}
              className="absolute right-1 top-1 h-8 w-8 p-0"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground text-center mt-2">
          AI agents can make mistakes. Consider checking important information.
        </p>
      </div>
    </div>
  )
}
