import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/lib/providers'
import { Toaster } from 'sonner'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'OneShotVoiceAgent - AI Agent Platform',
  description: 'Production-ready AI Agent Platform with real-time voice interaction, persistent memory, and comprehensive agent building capabilities',
  keywords: 'AI, voice agent, chatbot, LiveKit, Next.js, LangGraph, ElevenLabs',
  authors: [{ name: 'OneShotVoiceAgent Team' }],
  creator: 'OneShotVoiceAgent',
  publisher: 'OneShotVoiceAgent',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: '/',
    title: 'OneShotVoiceAgent',
    description: 'AI Agent Platform with Voice Interaction',
    siteName: 'OneShotVoiceAgent',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'OneShotVoiceAgent',
    description: 'AI Agent Platform with Voice Interaction',
    creator: '@oneshot_voice',
  },
  robots: {
    index: false, // Don't index in development
    follow: false,
    googleBot: {
      index: false,
      follow: false,
    },
  },
  icons: {
    icon: '/favicon.ico',
    other: {
      rel: 'icon',
      url: '/favicon.svg',
      type: 'image/svg+xml',
    },
  },
  manifest: '/manifest.json',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <meta name="theme-color" content="#3b82f6" />
      </head>
      <body className={inter.className} suppressHydrationWarning>
        <Providers>
          <div className="min-h-screen bg-background">
            {children}
          </div>
          <Toaster
            position="top-right"
            closeButton
            richColors
            theme="system"
          />
        </Providers>
      </body>
    </html>
  )
}