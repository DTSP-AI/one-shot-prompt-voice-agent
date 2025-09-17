import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { Bot, Settings, Sparkles } from 'lucide-react'

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 flex">
          <Link href="/" className="mr-6 flex items-center space-x-2">
            <Bot className="h-6 w-6" />
            <span className="font-bold">OneShotVoiceAgent</span>
          </Link>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            <Link
              href="/build"
              className="transition-colors hover:text-foreground/80 text-foreground/60"
            >
              Build Agent
            </Link>
            <Link
              href="/chat"
              className="transition-colors hover:text-foreground/80 text-foreground/60"
            >
              Voice Chat
            </Link>
            <Link
              href="/build"
              className="transition-colors hover:text-foreground/80 text-foreground/60"
            >
              Features
            </Link>
          </nav>
        </div>
        <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
          <nav className="flex items-center space-x-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/build">
                <Sparkles className="h-4 w-4 mr-2" />
                New Agent
              </Link>
            </Button>
            <ThemeToggle />
            <Button variant="ghost" size="icon" asChild>
              <Link href="/build">
                <Settings className="h-4 w-4" />
              </Link>
            </Button>
          </nav>
        </div>
      </div>
    </header>
  )
}