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
  Copy,
  RefreshCw
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
  isTyping?: boolean
}

interface Agent {
  id: string
  config: {
    payload: {
      name: string
      shortDescription: string
      voice: {
        elevenlabsVoiceId: string
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
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (agent && !conversationId) {
      // Start with a welcome message for new conversations
      const welcomeMessage: Message = {
        id: 'welcome',
        content: `Hello! I'm ${agent.config.payload.name}. ${agent.config.payload.shortDescription} How can I help you today?`,
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages([welcomeMessage])
    }
  }, [agent, conversationId])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !agent || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputMessage.trim(),
      role: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)

    // Add typing indicator
    const typingMessage: Message = {
      id: 'typing',
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      isTyping: true
    }
    setMessages(prev => [...prev, typingMessage])

    try {
      // TODO: Replace with actual agent chat API
      // For now, simulate a response
      await new Promise(resolve => setTimeout(resolve, 1500))

      const responses = [
        "Listen, that's actually a really interesting question. Let me break this down for you with some real science...",
        "*burp* Oh great, another one who thinks they understand the universe. Let me explain why you're wrong...",
        "You know what? That's not completely stupid. Here's what you need to understand about quantum mechanics...",
        "Wubba lubba dub dub! But seriously, your question touches on some fundamental principles of...",
        "Look, I've been to 47 different dimensions, and in every single one, the answer is..."
      ]

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: responses[Math.floor(Math.random() * responses.length)],
        role: 'assistant',
        timestamp: new Date()
      }

      // Remove typing indicator and add actual response
      setMessages(prev => prev.filter(m => m.id !== 'typing').concat(assistantMessage))
    } catch (error) {
      console.error('Failed to send message:', error)
      toast.error('Failed to send message')
      setMessages(prev => prev.filter(m => m.id !== 'typing'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleVoiceToggle = () => {
    setIsListening(!isListening)
    // TODO: Implement speech recognition
    toast.info(isListening ? 'Stopped listening' : 'Started listening')
  }

  const handleSpeakToggle = () => {
    setIsSpeaking(!isSpeaking)
    // TODO: Implement text-to-speech
    toast.info(isSpeaking ? 'Stopped speaking' : 'Started speaking')
  }

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content)
    toast.success('Message copied to clipboard')
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
      {/* Chat Header */}
      <div className="flex items-center gap-3 p-4 border-b bg-background/95 backdrop-blur">
        <Avatar className="h-10 w-10">
          <AvatarImage src={agent.config.payload.avatar || (agent.config.payload.name.toLowerCase().includes('rick') ? '/assets/avatars/rick_avatar.png' : undefined)} />
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
            variant={isSpeaking ? "default" : "outline"}
            onClick={handleSpeakToggle}
          >
            {isSpeaking ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </Button>
          <Badge variant="secondary">Online</Badge>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex gap-3 max-w-4xl",
              message.role === 'user' ? 'ml-auto flex-row-reverse' : ''
            )}
          >
            <Avatar className="h-8 w-8 flex-shrink-0">
              <AvatarFallback>
                {message.role === 'user' ? (
                  <User className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </AvatarFallback>
            </Avatar>
            <Card className={cn(
              "flex-1",
              message.role === 'user' ? 'bg-primary text-primary-foreground' : ''
            )}>
              <CardContent className="p-3">
                {message.isTyping ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">
                      {agent.config.payload.name} is typing...
                    </span>
                  </div>
                ) : (
                  <div>
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/50">
                      <span className="text-xs opacity-70">
                        {message.timestamp.toLocaleTimeString()}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => copyMessage(message.content)}
                        className="h-6 w-6 p-0"
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t p-4 bg-background/95 backdrop-blur">
        <div className="flex items-center gap-2 max-w-4xl mx-auto">
          <Button
            size="sm"
            variant={isListening ? "default" : "outline"}
            onClick={handleVoiceToggle}
          >
            {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          </Button>
          <div className="flex-1 relative">
            <Input
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={`Message ${agent.config.payload.name}...`}
              disabled={isLoading}
              className="pr-12"
            />
            <Button
              size="sm"
              onClick={handleSendMessage}
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