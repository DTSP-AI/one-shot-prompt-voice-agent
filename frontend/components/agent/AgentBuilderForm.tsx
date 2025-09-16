'use client'

import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Bot, Play, Volume2, Upload, User } from 'lucide-react'

const agentSchema = z.object({
  name: z.string().min(1, 'Agent name is required'),
  shortDescription: z.string().min(1, 'Short description is required'),
  characterDescription: z.object({
    physicalAppearance: z.string().optional(),
    identity: z.string().optional(),
    interactionStyle: z.string().optional(),
  }).optional(),
  mission: z.string().optional(),
  knowledge: z.object({
    urls: z.array(z.string()),
    files: z.array(z.string()),
  }),
  voice: z.object({
    elevenlabsVoiceId: z.string().min(1, 'Voice selection is required'),
  }),
  traits: z.object({
    creativity: z.number().min(0).max(100),
    empathy: z.number().min(0).max(100),
    assertiveness: z.number().min(0).max(100),
    sarcasm: z.number().min(0).max(100),
    verbosity: z.number().min(0).max(100),
    formality: z.number().min(0).max(100),
    confidence: z.number().min(0).max(100),
    humor: z.number().min(0).max(100),
    technicality: z.number().min(0).max(100),
    safety: z.number().min(0).max(100),
  }),
  avatar: z.string().optional(),
})

type AgentFormData = z.infer<typeof agentSchema>

// Pre-populated ElevenLabs voices
const DEFAULT_VOICES = [
  { voice_id: 'Rachel', name: 'Rachel (Calm, Feminine)' },
  { voice_id: 'Drew', name: 'Drew (Warm, Masculine)' },
  { voice_id: 'Clyde', name: 'Clyde (Authoritative, Masculine)' },
  { voice_id: 'Bella', name: 'Bella (Expressive, Feminine)' },
  { voice_id: 'Antoni', name: 'Antoni (Deep, Masculine)' },
  { voice_id: 'Elli', name: 'Elli (Youthful, Feminine)' },
  { voice_id: 'Josh', name: 'Josh (Friendly, Masculine)' },
  { voice_id: 'Arnold', name: 'Arnold (Crisp, Masculine)' },
  { voice_id: 'Adam', name: 'Adam (Deep, Masculine)' },
  { voice_id: 'Sam', name: 'Sam (Raspy, Masculine)' },
  { voice_id: 'custom', name: '🎙️ Custom Voice ID' }
]

export function AgentBuilderForm() {
  const [manualVoiceId, setManualVoiceId] = useState('')
  const [voices, setVoices] = useState<{voice_id: string, name: string}[]>(DEFAULT_VOICES)
  const [isLoadingVoices, setIsLoadingVoices] = useState(false)
  const [showCustomInput, setShowCustomInput] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<AgentFormData>({
    resolver: zodResolver(agentSchema),
    defaultValues: {
      name: '',
      shortDescription: '',
      characterDescription: {
        physicalAppearance: '',
        identity: '',
        interactionStyle: '',
      },
      mission: '',
      knowledge: {
        urls: [],
        files: [],
      },
      voice: {
        elevenlabsVoiceId: '',
      },
      traits: {
        creativity: 50,
        empathy: 50,
        assertiveness: 50,
        sarcasm: 20,
        verbosity: 50,
        formality: 50,
        confidence: 50,
        humor: 30,
        technicality: 50,
        safety: 80,
      },
      avatar: '',
    },
  })

  const traits = watch('traits')

  const handlePreviewVoice = async (voiceId: string) => {
    try {
      const response = await fetch('/api/v1/voices/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voice_id: voiceId,
          text: "Hello! This is how I would sound as your AI agent."
        }),
      })

      const data = await response.json()
      if (data.success && data.audio_b64) {
        const audio = new Audio(`data:audio/mpeg;base64,${data.audio_b64}`)
        audio.play()
      } else {
        console.error('Voice preview failed:', data.error || 'Unknown error')
        alert(`Voice preview failed: ${data.error || 'ElevenLabs API may not be configured'}`)
      }
    } catch (error) {
      console.error('Failed to preview voice:', error)
      alert('Failed to preview voice. Please check if ElevenLabs API is configured.')
    }
  }

  const loadVoices = async () => {
    setIsLoadingVoices(true)
    try {
      const response = await fetch('/api/v1/voices/elevenlabs')
      if (response.ok) {
        const data = await response.json()
        if (data.success && data.voices) {
          // Merge backend voices with default voices, add custom option
          const backendVoices = data.voices.map((v: any) => ({
            voice_id: v.voice_id,
            name: `${v.name} (Custom)`
          }))
          setVoices([...DEFAULT_VOICES.slice(0, -1), ...backendVoices, DEFAULT_VOICES[DEFAULT_VOICES.length - 1]])
        } else {
          console.warn('Backend voices unavailable, using default voices')
          setVoices(DEFAULT_VOICES)
        }
      } else {
        console.warn('Backend not available, using default ElevenLabs voices')
        setVoices(DEFAULT_VOICES)
      }
    } catch (error) {
      console.warn('Failed to load backend voices, using defaults:', error)
      setVoices(DEFAULT_VOICES)
    } finally {
      setIsLoadingVoices(false)
    }
  }

  React.useEffect(() => {
    loadVoices()
  }, [])

  const onSubmit = async (data: AgentFormData) => {
    try {
      console.log('📦 Agent payload:', data)

      // Send to backend API
      const response = await fetch('/api/v1/agents/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to create agent')
      }

      const result = await response.json()
      console.log('✅ Agent created successfully:', result)

      // TODO: Show success message and redirect to agent list or details
      alert(`Agent "${data.name}" created successfully!`)
    } catch (error) {
      console.error('❌ Failed to create agent:', error)
      alert(`Failed to create agent: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const TraitSlider = ({
    name,
    label,
    value,
    onChange
  }: {
    name: keyof AgentFormData['traits']
    label: string
    value: number
    onChange: (value: number) => void
  }) => (
    <div className="space-y-2">
      <div className="flex justify-between">
        <Label htmlFor={name}>{label}</Label>
        <span className="text-sm text-muted-foreground">{value}/100</span>
      </div>
      <Slider
        id={name}
        min={0}
        max={100}
        step={1}
        value={[value]}
        onValueChange={(values) => onChange(values[0])}
        className="w-full"
      />
    </div>
  )

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Bot className="h-8 w-8" />
          Agent Builder
        </h1>
        <p className="text-muted-foreground">Create your custom AI agent with personality and voice</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
        {/* Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="name">Agent Name</Label>
              <Input
                id="name"
                {...register('name')}
                placeholder="e.g., Alex the Assistant"
              />
              {errors.name && (
                <p className="text-sm text-destructive mt-1">{errors.name.message}</p>
              )}
            </div>

            <div>
              <Label htmlFor="shortDescription">Short Description</Label>
              <Input
                id="shortDescription"
                {...register('shortDescription')}
                placeholder="Brief description of the agent's role"
              />
              {errors.shortDescription && (
                <p className="text-sm text-destructive mt-1">{errors.shortDescription.message}</p>
              )}
            </div>

            <div>
              <Label htmlFor="mission">Mission (Optional)</Label>
              <Textarea
                id="mission"
                {...register('mission')}
                placeholder="What is this agent's primary goal?"
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        {/* Character Description */}
        <Card>
          <CardHeader>
            <CardTitle>Character Description</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="identity">Identity</Label>
              <Textarea
                id="identity"
                {...register('characterDescription.identity')}
                placeholder="Who is this agent? Background, expertise, personality..."
                rows={3}
              />
            </div>

            <div>
              <Label htmlFor="interactionStyle">Interaction Style</Label>
              <Textarea
                id="interactionStyle"
                {...register('characterDescription.interactionStyle')}
                placeholder="How does this agent communicate and interact?"
                rows={2}
              />
            </div>

            <div>
              <Label htmlFor="physicalAppearance">Physical Appearance (Optional)</Label>
              <Textarea
                id="physicalAppearance"
                {...register('characterDescription.physicalAppearance')}
                placeholder="Visual description of the agent"
                rows={2}
              />
            </div>
          </CardContent>
        </Card>

        {/* Avatar Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Avatar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Avatar Selection - Simplified */}
            <div className="space-y-2">
              <Label htmlFor="avatar">Avatar URL (Optional)</Label>
              <Input
                id="avatar"
                placeholder="Enter avatar image URL"
                {...register('avatar')}
                className="w-full"
              />
              <p className="text-sm text-muted-foreground">Leave empty for default avatar</p>
            </div>
          </CardContent>
        </Card>

        {/* Personality Traits */}
        <Card>
          <CardHeader>
            <CardTitle>Personality Traits (0-100)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <TraitSlider
                name="creativity"
                label="Creativity"
                value={traits.creativity}
                onChange={(value) => setValue('traits.creativity', value)}
              />
              <TraitSlider
                name="empathy"
                label="Empathy"
                value={traits.empathy}
                onChange={(value) => setValue('traits.empathy', value)}
              />
              <TraitSlider
                name="assertiveness"
                label="Assertiveness"
                value={traits.assertiveness}
                onChange={(value) => setValue('traits.assertiveness', value)}
              />
              <TraitSlider
                name="sarcasm"
                label="Sarcasm"
                value={traits.sarcasm}
                onChange={(value) => setValue('traits.sarcasm', value)}
              />
              <TraitSlider
                name="verbosity"
                label="Verbosity"
                value={traits.verbosity}
                onChange={(value) => setValue('traits.verbosity', value)}
              />
              <TraitSlider
                name="formality"
                label="Formality"
                value={traits.formality}
                onChange={(value) => setValue('traits.formality', value)}
              />
              <TraitSlider
                name="confidence"
                label="Confidence"
                value={traits.confidence}
                onChange={(value) => setValue('traits.confidence', value)}
              />
              <TraitSlider
                name="humor"
                label="Humor"
                value={traits.humor}
                onChange={(value) => setValue('traits.humor', value)}
              />
              <TraitSlider
                name="technicality"
                label="Technicality"
                value={traits.technicality}
                onChange={(value) => setValue('traits.technicality', value)}
              />
              <TraitSlider
                name="safety"
                label="Safety"
                value={traits.safety}
                onChange={(value) => setValue('traits.safety', value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Voice Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Voice Selection</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Select Voice</Label>
              <div className="flex gap-2">
                <Select
                  value={showCustomInput ? 'custom' : watch('voice.elevenlabsVoiceId')}
                  onValueChange={(value) => {
                    if (value === 'custom') {
                      setShowCustomInput(true)
                      setValue('voice.elevenlabsVoiceId', '')
                    } else {
                      setShowCustomInput(false)
                      setValue('voice.elevenlabsVoiceId', value)
                    }
                  }}
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Choose a voice" />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingVoices ? (
                      <SelectItem value="loading" disabled>Loading voices...</SelectItem>
                    ) : (
                      voices.map((voice) => (
                        <SelectItem key={voice.voice_id} value={voice.voice_id}>
                          {voice.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                {watch('voice.elevenlabsVoiceId') && !showCustomInput && (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => handlePreviewVoice(watch('voice.elevenlabsVoiceId'))}
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                )}
              </div>
              {errors.voice?.elevenlabsVoiceId && (
                <p className="text-sm text-destructive mt-1">{errors.voice.elevenlabsVoiceId.message}</p>
              )}
            </div>

            {showCustomInput && (
              <div>
                <Label htmlFor="customVoiceId">Custom ElevenLabs Voice ID</Label>
                <div className="flex gap-2">
                  <Input
                    id="customVoiceId"
                    value={manualVoiceId}
                    onChange={(e) => setManualVoiceId(e.target.value)}
                    placeholder="Enter your ElevenLabs Voice ID (e.g. PpJ5oHQDnyCAOSi5tDHn)"
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      if (manualVoiceId.trim()) {
                        setValue('voice.elevenlabsVoiceId', manualVoiceId.trim())
                      }
                    }}
                    disabled={!manualVoiceId.trim()}
                  >
                    Apply
                  </Button>
                  {manualVoiceId.trim() && (
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      onClick={() => handlePreviewVoice(manualVoiceId.trim())}
                    >
                      <Volume2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  Find your Voice ID in your ElevenLabs account dashboard
                </p>
              </div>
            )}

          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex justify-end">
          <Button type="submit" size="lg" className="px-8">
            Create Agent
          </Button>
        </div>
      </form>
    </div>
  )
}