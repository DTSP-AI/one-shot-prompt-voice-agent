declare global {
  interface Window {
    // Add any custom window properties here
    electron?: any;
    webkitSpeechRecognition?: any;
    SpeechRecognition?: any;
    webkitAudioContext?: any;
    AudioContext?: any;
  }

  // Browser API extensions
  interface Navigator {
    webkitGetUserMedia?: any;
    mozGetUserMedia?: any;
    getUserMedia?: any;
  }

  // Custom global types
  type MCPServerStatus = 'enabled' | 'disabled' | 'degraded' | 'unconfigured';
  type AgentStatus = 'created' | 'active' | 'paused' | 'error';

  // Environment variables
  namespace NodeJS {
    interface ProcessEnv {
      NEXT_PUBLIC_API_URL: string;
      NEXT_PUBLIC_WS_URL: string;
      NODE_ENV: 'development' | 'production' | 'test';
    }
  }
}

export {};