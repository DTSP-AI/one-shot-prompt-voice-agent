import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Header } from '@/components/layout/Header'
import {
  Bot,
  Mic,
  Brain,
  Zap,
  Settings,
  MessageSquare,
  Sparkles,
  Play,
  ChevronRight
} from 'lucide-react'

export default function HomePage() {
  const features = [
    {
      icon: Bot,
      title: "Agent Logic",
      description: "Your agents maintain unwavering character consistency across every interaction. They respond naturally with their unique personality, communication style, and expertise level, creating authentic relationships that users can depend on.",
      href: "/build"
    },
    {
      icon: Mic,
      title: "Voice & Vision",
      description: "Experience crystal-clear, natural conversations with studio-quality voice synthesis and lightning-fast speech recognition. Your agents sound human, respond instantly, and handle complex audio interactions seamlessly.",
      href: "/chat"
    },
    {
      icon: Brain,
      title: "Memory",
      description: "Consistent autobiographical memory, episodic memory, semantic memory, and procedural memory. Your agents learn through interactions and positive reinforcement on the job, growing smarter with every conversation.",
      href: "/build"
    },
    {
      icon: Settings,
      title: "MCP Connectors",
      description: "Connect your agents to the world through Model Context Protocol. Enable web search, file operations, database queries, API integrations, and custom tools without complex development.",
      href: "/build"
    }
  ]

  const quickActions = [
    {
      title: "Create New Agent",
      description: "Build your first AI agent",
      href: "/build",
      icon: Sparkles,
      color: "primary"
    },
    {
      title: "Join Voice Chat",
      description: "Start talking to an agent",
      href: "/chat",
      icon: Play,
      color: "secondary"
    }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-secondary/20">
      <Header />

      <main className="container mx-auto px-4 py-12">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 bg-primary/10 text-primary px-3 py-1 rounded-full text-sm font-medium mb-6">
            <Zap className="h-4 w-4" />
            Production Ready
          </div>

          <h1 className="text-4xl md:text-6xl font-bold bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent mb-6">
            OneShotVoiceAgent
          </h1>

          <p className="text-xl text-muted-foreground mb-8 max-w-3xl mx-auto">
            Production-ready AI Agent Platform with real-time voice interaction,
            persistent memory, theme switching, and comprehensive agent building capabilities.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <Button size="lg" asChild className="group">
              <Link href="/build">
                <Sparkles className="h-5 w-5 mr-2" />
                Create Agent
                <ChevronRight className="h-4 w-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </Link>
            </Button>

            <Button size="lg" variant="outline" asChild>
              <Link href="/chat">
                <MessageSquare className="h-5 w-5 mr-2" />
                Start Chatting
              </Link>
            </Button>
          </div>

        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-2 gap-6 mb-16">
          {quickActions.map((action) => (
            <Link key={action.title} href={action.href}>
              <Card className="agent-card cursor-pointer border-2 hover:border-primary/50">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg">
                      <action.icon className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{action.title}</CardTitle>
                      <CardDescription>{action.description}</CardDescription>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>

        {/* Features Grid */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold text-center mb-12">
            Platform Features
          </h2>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature) => (
              <Link key={feature.title} href={feature.href}>
                <Card className="agent-card cursor-pointer h-full">
                  <CardHeader className="text-center">
                    <div className="mx-auto p-3 bg-primary/10 rounded-full w-fit mb-4">
                      <feature.icon className="h-8 w-8 text-primary" />
                    </div>
                    <CardTitle className="text-lg">{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-center">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        {/* Get Started */}
        <div className="text-center">
          <Button variant="outline" asChild>
            <Link href="/build">
              Build Your Agent
              <ChevronRight className="h-4 w-4 ml-2" />
            </Link>
          </Button>
        </div>
      </main>
    </div>
  )
}