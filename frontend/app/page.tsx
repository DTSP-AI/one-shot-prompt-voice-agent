'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Mic, Video, Settings, Users, Activity, ArrowRight, Shield, Zap, Brain } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { StatusBar } from '@/components/StatusBar';
import { api } from '@/lib/api';
import { toast } from 'sonner';

export default function HomePage() {
  const router = useRouter();
  const [roomName, setRoomName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [systemHealth, setSystemHealth] = useState<any>(null);

  useEffect(() => {
    // Load defaults from localStorage
    const savedRoomName = localStorage.getItem('voice-agent-room') || process.env.NEXT_PUBLIC_DEFAULT_ROOM || 'agent-room';
    const savedDisplayName = localStorage.getItem('voice-agent-name') || 'User';
    
    setRoomName(savedRoomName);
    setDisplayName(savedDisplayName);

    // Check system health
    checkSystemHealth();
  }, []);

  const checkSystemHealth = async () => {
    try {
      const health = await api.getHealth();
      setSystemHealth(health);
    } catch (error) {
      console.error('Health check failed:', error);
      toast.error('Unable to connect to backend services');
    }
  };

  const handleJoinRoom = async () => {
    if (!roomName.trim() || !displayName.trim()) {
      toast.error('Please enter both room name and display name');
      return;
    }

    setIsConnecting(true);

    try {
      // Save to localStorage
      localStorage.setItem('voice-agent-room', roomName);
      localStorage.setItem('voice-agent-name', displayName);

      // Navigate to room
      router.push(`/room/${encodeURIComponent(roomName)}?name=${encodeURIComponent(displayName)}`);
    } catch (error) {
      console.error('Failed to join room:', error);
      toast.error('Failed to join room. Please try again.');
      setIsConnecting(false);
    }
  };

  const features = [
    {
      icon: Brain,
      title: 'AI-Powered Conversation',
      description: 'Advanced LangGraph agents with specialized roles (Supervisor, Orchestrator, Coder, QA, Deployer)',
      color: 'text-voice-primary',
    },
    {
      icon: Mic,
      title: 'Real-time Speech',
      description: 'Deepgram STT and ElevenLabs TTS for natural voice interaction with low latency',
      color: 'text-voice-secondary',
    },
    {
      icon: Video,
      title: 'Vision Processing',
      description: 'Upload images for AI analysis and get detailed descriptions and insights',
      color: 'text-voice-accent',
    },
    {
      icon: Shield,
      title: 'Persistent Memory',
      description: 'Mem0 integration maintains context across conversations with project namespacing',
      color: 'text-voice-success',
    },
    {
      icon: Zap,
      title: 'LiveKit Integration',
      description: 'Professional-grade WebRTC for crystal-clear audio and reliable connections',
      color: 'text-voice-warning',
    },
    {
      icon: Users,
      title: 'Multi-Agent System',
      description: 'Intelligent routing between specialized agents based on conversation context',
      color: 'text-voice-error',
    },
  ];

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center space-y-4"
      >
        <h1 className="text-4xl md:text-6xl font-bold bg-gradient-to-r from-voice-primary via-voice-secondary to-voice-accent bg-clip-text text-transparent">
          Voice Agent Studio
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Experience the future of AI conversation with our LiveKit-powered LangGraph voice agent. 
          Real-time speech, vision processing, and intelligent multi-agent orchestration.
        </p>
        
        {/* Status Bar */}
        <div className="flex justify-center">
          <StatusBar health={systemHealth} />
        </div>
      </motion.div>

      {/* Join Room Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="max-w-md mx-auto"
      >
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="flex items-center justify-center space-x-2">
              <Activity className="h-5 w-5 text-voice-primary" />
              <span>Join Voice Session</span>
            </CardTitle>
            <CardDescription>
              Start a conversation with the AI agent
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="displayName" className="text-sm font-medium">
                Your Name
              </label>
              <Input
                id="displayName"
                placeholder="Enter your name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isConnecting}
              />
            </div>
            
            <div className="space-y-2">
              <label htmlFor="roomName" className="text-sm font-medium">
                Room Name
              </label>
              <Input
                id="roomName"
                placeholder="Enter room name"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                disabled={isConnecting}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isConnecting) {
                    handleJoinRoom();
                  }
                }}
              />
            </div>

            <Button
              onClick={handleJoinRoom}
              disabled={isConnecting || !roomName.trim() || !displayName.trim()}
              className="w-full voice-button-primary h-12 text-lg"
            >
              {isConnecting ? (
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Connecting...</span>
                </div>
              ) : (
                <div className="flex items-center space-x-2">
                  <span>Join Room</span>
                  <ArrowRight className="h-4 w-4" />
                </div>
              )}
            </Button>

            <div className="text-center">
              <Button
                variant="ghost"
                onClick={() => router.push('/settings')}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                <Settings className="h-4 w-4 mr-2" />
                Advanced Settings
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Features Grid */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="space-y-6"
      >
        <h2 className="text-2xl font-bold text-center">Platform Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 + index * 0.1 }}
            >
              <Card className="h-full hover:shadow-lg transition-shadow duration-300">
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <feature.icon className={`h-6 w-6 ${feature.color}`} />
                    <span className="text-lg">{feature.title}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base leading-relaxed">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* System Status */}
      {systemHealth && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="max-w-2xl mx-auto"
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>System Status</span>
                <Badge variant={systemHealth.status === 'healthy' ? 'default' : 'destructive'}>
                  {systemHealth.status}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                {Object.entries(systemHealth.services || {}).map(([service, status]: [string, any]) => (
                  <div key={service} className="flex items-center space-x-2">
                    <div 
                      className={`w-2 h-2 rounded-full ${
                        status.status === 'healthy' ? 'bg-green-500' :
                        status.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                    />
                    <span className="capitalize">{service}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="text-center text-muted-foreground text-sm space-y-2"
      >
        <p>
          Powered by{' '}
          <a href="https://livekit.io" target="_blank" rel="noopener noreferrer" className="text-voice-primary hover:underline">
            LiveKit
          </a>
          {' '}&bull;{' '}
          <a href="https://github.com/langchain-ai/langgraph" target="_blank" rel="noopener noreferrer" className="text-voice-secondary hover:underline">
            LangGraph
          </a>
          {' '}&bull;{' '}
          <a href="https://deepgram.com" target="_blank" rel="noopener noreferrer" className="text-voice-accent hover:underline">
            Deepgram
          </a>
          {' '}&bull;{' '}
          <a href="https://elevenlabs.io" target="_blank" rel="noopener noreferrer" className="text-voice-success hover:underline">
            ElevenLabs
          </a>
        </p>
        <p>
          Built with Next.js, TypeScript, and Tailwind CSS
        </p>
      </motion.div>
    </div>
  );
}