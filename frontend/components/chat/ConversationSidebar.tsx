'use client'

import React, { useState, useEffect } from 'react'
import { useApi } from '@/lib/api-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  MessageSquare,
  Plus,
  Menu,
  X,
  Bot,
  Calendar,
  Trash2,
  MoreHorizontal
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface Conversation {
  id: string
  agentId: string
  title: string
  lastMessage: string
  updatedAt: string
  messageCount: number
}

interface ConversationSidebarProps {
  isOpen: boolean
  onToggle: () => void
  selectedConversationId?: string
  onConversationSelect: (conversationId: string) => void
  onNewConversation: () => void
  agentId?: string
}

export function ConversationSidebar({
  isOpen,
  onToggle,
  selectedConversationId,
  onConversationSelect,
  onNewConversation,
  agentId
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(false)
  const api = useApi()

  useEffect(() => {
    if (agentId) {
      loadConversations()
    }
  }, [agentId])

  const loadConversations = async () => {
    if (!agentId) return

    try {
      setLoading(true)
      // TODO: Replace with actual API call when conversations endpoint is implemented
      const response = await api.get<{success: boolean, conversations: Conversation[]}>(`/api/v1/agents/${agentId}/conversations`)

      if (response.success) {
        setConversations(response.conversations)
      } else {
        setConversations([])
      }
    } catch (error) {
      console.error('Failed to load conversations:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60))

    if (diffInHours < 1) return 'Just now'
    if (diffInHours < 24) return `${diffInHours}h ago`
    if (diffInHours < 168) return `${Math.floor(diffInHours / 24)}d ago`
    return date.toLocaleDateString()
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        'fixed left-0 top-0 h-full bg-background border-r z-50 transition-transform duration-300 ease-in-out',
        'lg:relative lg:translate-x-0 lg:z-auto',
        isOpen ? 'translate-x-0' : '-translate-x-full',
        'w-80'
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-lg">Conversations</h2>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={onNewConversation}>
              <Plus className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="ghost" onClick={onToggle} className="lg:hidden">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="p-4 text-center text-muted-foreground">
              Loading conversations...
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-3">
                No conversations yet
              </p>
              <Button size="sm" onClick={onNewConversation}>
                <Plus className="h-4 w-4 mr-2" />
                Start New Chat
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {conversations.map((conversation) => (
                <Card
                  key={conversation.id}
                  className={cn(
                    'cursor-pointer transition-all hover:shadow-sm',
                    selectedConversationId === conversation.id ? 'ring-2 ring-primary' : ''
                  )}
                  onClick={() => onConversationSelect(conversation.id)}
                >
                  <CardContent className="p-3">
                    <div className="flex items-start gap-3">
                      <Avatar className="h-8 w-8 flex-shrink-0">
                        <AvatarImage src="/assets/avatars/rick_avatar.png" />
                        <AvatarFallback>
                          <Bot className="h-4 w-4" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="font-medium text-sm truncate">
                            {conversation.title}
                          </h4>
                          <Badge variant="secondary" className="text-xs ml-2">
                            {conversation.messageCount}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                          {conversation.lastMessage}
                        </p>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">
                            {formatTimeAgo(conversation.updatedAt)}
                          </span>
                          <Button size="sm" variant="ghost" className="h-6 w-6 p-0">
                            <MoreHorizontal className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t">
          <Button variant="outline" size="sm" className="w-full" asChild>
            <a href="/build">
              <Bot className="h-4 w-4 mr-2" />
              Create New Agent
            </a>
          </Button>
        </div>
      </div>

      {/* Mobile hamburger button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggle}
        className="fixed top-4 left-4 z-30 lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </Button>
    </>
  )
}