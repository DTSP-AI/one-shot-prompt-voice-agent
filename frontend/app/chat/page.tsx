'use client'

import React, { useState, useEffect } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { useLiveKit } from '@/lib/livekit-provider'
import { Mic, MicOff, Volume2, VolumeX, Phone, PhoneOff, Settings, Users } from 'lucide-react'

export default function VoiceChatPage() {
  const { room, isConnected, connect, disconnect, error } = useLiveKit()
  const [roomName, setRoomName] = useState('voice-chat-' + Date.now())
  const [participantName, setParticipantName] = useState('User')
  const [isAudioEnabled, setIsAudioEnabled] = useState(true)
  const [isConnecting, setIsConnecting] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  // Generate participant name with random ID if empty
  useEffect(() => {
    if (!participantName || participantName === 'User') {
      setParticipantName(`User-${Math.random().toString(36).substr(2, 6)}`)
    }
  }, [])

  const handleConnect = async () => {
    try {
      setIsConnecting(true)
      setConnectionError(null)

      // Get LiveKit token from backend
      const tokenResponse = await fetch(`/api/v1/livekit/token?room=${roomName}&identity=${participantName}`)
      const tokenData = await tokenResponse.json()

      if (!tokenData.success) {
        throw new Error(tokenData.detail || 'Failed to get token')
      }

      // Connect to LiveKit room
      await connect(tokenData.url, tokenData.token)

      // Enable audio by default
      if (room) {
        await room.localParticipant.setMicrophoneEnabled(isAudioEnabled)
      }

    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection failed'
      setConnectionError(message)
      console.error('Connection error:', err)
    } finally {
      setIsConnecting(false)
    }
  }

  const handleDisconnect = () => {
    disconnect()
    setConnectionError(null)
  }

  const toggleAudio = async () => {
    if (room) {
      const newState = !isAudioEnabled
      await room.localParticipant.setMicrophoneEnabled(newState)
      setIsAudioEnabled(newState)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-secondary/20">
      <Header />

      <main className="container mx-auto px-4 py-12">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-4">Voice Chat</h1>
            <p className="text-muted-foreground text-lg">
              Real-time voice conversation with AI agents using LiveKit
            </p>
          </div>

          {/* Connection Status */}
          <div className="mb-8 text-center">
            <Badge variant={isConnected ? "default" : "secondary"} className="text-sm px-4 py-2">
              {isConnected ? (
                <>
                  <Volume2 className="h-4 w-4 mr-2" />
                  Connected to {roomName}
                </>
              ) : (
                <>
                  <VolumeX className="h-4 w-4 mr-2" />
                  Not Connected
                </>
              )}
            </Badge>
          </div>

          {/* Connection Card */}
          {!isConnected ? (
            <Card className="mb-8">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Phone className="h-5 w-5" />
                  Join Voice Chat
                </CardTitle>
                <CardDescription>
                  Enter room details to start voice conversation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="roomName">Room Name</Label>
                    <Input
                      id="roomName"
                      value={roomName}
                      onChange={(e) => setRoomName(e.target.value)}
                      placeholder="voice-chat-room"
                    />
                  </div>
                  <div>
                    <Label htmlFor="participantName">Your Name</Label>
                    <Input
                      id="participantName"
                      value={participantName}
                      onChange={(e) => setParticipantName(e.target.value)}
                      placeholder="Enter your name"
                    />
                  </div>
                </div>

                {(connectionError || error) && (
                  <div className="text-destructive text-sm bg-destructive/10 p-3 rounded-md">
                    ⚠️ {connectionError || error}
                  </div>
                )}

                <Button
                  onClick={handleConnect}
                  disabled={isConnecting || !roomName || !participantName}
                  className="w-full"
                  size="lg"
                >
                  {isConnecting ? (
                    <>
                      <div className="spinner w-4 h-4 mr-2" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <Phone className="h-4 w-4 mr-2" />
                      Connect to Voice Chat
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          ) : (
            /* Connected Controls */
            <Card className="mb-8">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Voice Chat Controls
                </CardTitle>
                <CardDescription>
                  You are connected as <strong>{participantName}</strong> in room <strong>{roomName}</strong>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4 justify-center">
                  <Button
                    variant={isAudioEnabled ? "default" : "destructive"}
                    onClick={toggleAudio}
                    size="lg"
                  >
                    {isAudioEnabled ? (
                      <>
                        <Mic className="h-4 w-4 mr-2" />
                        Mute
                      </>
                    ) : (
                      <>
                        <MicOff className="h-4 w-4 mr-2" />
                        Unmute
                      </>
                    )}
                  </Button>

                  <Button
                    variant="destructive"
                    onClick={handleDisconnect}
                    size="lg"
                  >
                    <PhoneOff className="h-4 w-4 mr-2" />
                    Disconnect
                  </Button>

                  <Button variant="outline" size="lg">
                    <Settings className="h-4 w-4 mr-2" />
                    Settings
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Audio Elements Container */}
          <div id="audio-container" className="hidden">
            {/* Remote audio tracks will be appended here */}
          </div>

          {/* Info Cards */}
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">How it Works</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p>• Connect to a voice chat room using LiveKit</p>
                <p>• Your microphone input is streamed in real-time</p>
                <p>• AI agents can join and respond with voice</p>
                <p>• Uses Deepgram for speech-to-text</p>
                <p>• Uses ElevenLabs for text-to-speech</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Requirements</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p>• Microphone access permission</p>
                <p>• LiveKit server configuration</p>
                <p>• Stable internet connection</p>
                <p>• Modern web browser with WebRTC</p>
                <p>• ElevenLabs API key for TTS</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}