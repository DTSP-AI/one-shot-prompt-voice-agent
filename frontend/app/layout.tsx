import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import '@livekit/components-styles';
import { Providers } from '@/lib/providers';
import { Toaster } from 'sonner';

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-sans',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: 'LiveKit LangGraph Voice Agent',
  description: 'AI voice agent with real-time conversation, vision processing, and tool integration',
  keywords: ['AI', 'voice agent', 'LiveKit', 'LangGraph', 'real-time', 'conversation'],
  authors: [{ name: 'Voice Agent Team' }],
  creator: 'Voice Agent Team',
  publisher: 'Voice Agent Team',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:3000'),
  openGraph: {
    type: 'website',
    siteName: 'LiveKit LangGraph Voice Agent',
    title: 'LiveKit LangGraph Voice Agent',
    description: 'AI voice agent with real-time conversation, vision processing, and tool integration',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'LiveKit LangGraph Voice Agent',
    description: 'AI voice agent with real-time conversation, vision processing, and tool integration',
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
        <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/site.webmanifest" />
        <meta name="theme-color" content="#6366f1" />
        <meta name="color-scheme" content="dark light" />
      </head>
      <body 
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased min-h-screen bg-background text-foreground`}
        suppressHydrationWarning
      >
        <Providers>
          <div className="relative flex min-h-screen flex-col">
            <div className="flex-1">
              {children}
            </div>
          </div>
          <Toaster 
            position="top-right"
            expand={false}
            richColors
            closeButton
            toastOptions={{
              duration: 4000,
              style: {
                background: 'hsl(var(--background))',
                color: 'hsl(var(--foreground))',
                border: '1px solid hsl(var(--border))',
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}