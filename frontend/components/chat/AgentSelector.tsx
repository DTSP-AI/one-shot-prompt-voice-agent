'use client'

import React, { useState, useEffect } from 'react'
import { useApi } from '@/lib/api-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Bot, MessageSquare, Play, Loader2 } from 'lucide-react'

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

interface AgentSelectorProps {
  onAgentSelect: (agent: Agent) => void
  selectedAgentId?: string
}

export function AgentSelector({ onAgentSelect, selectedAgentId }: AgentSelectorProps) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const api = useApi()

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.get<{success: boolean, agents: Agent[], total: number}>('/api/v1/agents/')

      if (response.success) {
        setAgents(response.agents)
      } else {
        setError('Failed to load agents')
      }
    } catch (err) {
      console.error('Failed to load agents:', err)
      setError('Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading agents...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-red-500 mb-4">{error}</p>
        <Button onClick={loadAgents} variant="outline">
          Try Again
        </Button>
      </div>
    )
  }

  if (agents.length === 0) {
    return (
      <div className="p-8 text-center">
        <Bot className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
        <h3 className="text-lg font-semibold mb-2">No Agents Created</h3>
        <p className="text-muted-foreground mb-4">
          Create your first agent to start chatting
        </p>
        <Button asChild>
          <a href="/build">
            <Bot className="h-4 w-4 mr-2" />
            Create Agent
          </a>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Select an Agent</h2>
        <Badge variant="secondary">{agents.length} agents</Badge>
      </div>

      <div className="grid gap-3">
        {agents.map((agent) => (
          <Card
            key={agent.id}
            className={`cursor-pointer transition-all hover:shadow-md ${
              selectedAgentId === agent.id ? 'ring-2 ring-primary' : ''
            }`}
            onClick={() => onAgentSelect(agent)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={agent.config.payload.avatar || (agent.config.payload.name.toLowerCase().includes('rick') ? '/assets/avatars/rick_avatar.png' : undefined)} />
                  <AvatarFallback>
                    <Bot className="h-5 w-5" />
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-base truncate">
                    {agent.config.payload.name}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground truncate">
                    {agent.config.payload.shortDescription}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={agent.status === 'created' ? 'default' : 'secondary'}>
                    {agent.status}
                  </Badge>
                  <Button size="sm" variant="ghost">
                    <MessageSquare className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className="pt-4 border-t">
        <Button variant="outline" className="w-full" asChild>
          <a href="/build">
            <Bot className="h-4 w-4 mr-2" />
            Create New Agent
          </a>
        </Button>
      </div>
    </div>
  )
}