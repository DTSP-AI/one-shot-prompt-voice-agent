'use client'

import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { Header } from '@/components/layout/Header'
import { ConversationSidebar } from '@/components/chat/ConversationSidebar'
import { AgentSelector } from '@/components/chat/AgentSelector'
import { ChatInterface } from '@/components/chat/ChatInterface'
import { useApi } from '@/lib/api-provider'

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
  status: string
}

export default function ChatPage() {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [selectedConversationId, setSelectedConversationId] = useState<string | undefined>()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showAgentSelector, setShowAgentSelector] = useState(true)
  const searchParams = useSearchParams()
  const api = useApi()

  // Check for agent ID in URL params
  useEffect(() => {
    const agentId = searchParams.get('agent')
    if (agentId) {
      loadAgentById(agentId)
    }
  }, [searchParams])

  const loadAgentById = async (agentId: string) => {
    try {
      const response = await api.get<{success: boolean, agent: Agent}>(`/api/v1/agents/${agentId}`)
      if (response.success && response.agent) {
        setSelectedAgent(response.agent)
        setShowAgentSelector(false)
        setSidebarOpen(true)
      }
    } catch (error) {
      console.error('Failed to load agent:', error)
    }
  }

  const handleAgentSelect = (agent: Agent) => {
    setSelectedAgent(agent)
    setShowAgentSelector(false)
    setSidebarOpen(true)
    setSelectedConversationId(undefined) // Start new conversation
  }

  const handleConversationSelect = (conversationId: string) => {
    setSelectedConversationId(conversationId)
    setSidebarOpen(false) // Close sidebar on mobile after selection
  }

  const handleNewConversation = () => {
    setSelectedConversationId(undefined)
    setSidebarOpen(false) // Close sidebar on mobile after action
  }

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen)
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />

      <div className="flex-1 flex overflow-hidden">
        {/* Agent Selection Modal/Sidebar */}
        {showAgentSelector && (
          <div className="w-full lg:w-96 border-r bg-background p-4 overflow-y-auto">
            <AgentSelector
              onAgentSelect={handleAgentSelect}
              selectedAgentId={selectedAgent?.id}
            />
          </div>
        )}

        {/* Conversation Sidebar */}
        {!showAgentSelector && (
          <ConversationSidebar
            isOpen={sidebarOpen}
            onToggle={toggleSidebar}
            selectedConversationId={selectedConversationId}
            onConversationSelect={handleConversationSelect}
            onNewConversation={handleNewConversation}
            agentId={selectedAgent?.id}
          />
        )}

        {/* Main Chat Area */}
        <div className="flex-1 flex">
          {!showAgentSelector && (
            <ChatInterface
              agent={selectedAgent}
              conversationId={selectedConversationId}
            />
          )}
        </div>
      </div>
    </div>
  )
}