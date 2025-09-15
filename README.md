# OneShotVoiceAgent

## Quick Start (15-Minute Setup)

### Prerequisites
- **Python 3.11+** (Download from python.org)
- **Node.js 18+** (Download from nodejs.org)
- **Git** (for cloning repository)

### Automated Setup (Recommended)
```powershell
# Windows
.\scripts\setup.ps1

# After setup completes:
.\scripts\start-dev.ps1
```

### Manual Setup
```bash
# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Start servers (separate terminals)
cd backend && python main.py
cd frontend && npm run dev
```

### Environment Configuration

#### Backend Environment (`backend/.env`)
```env
# LiveKit Configuration (Required)
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_API_SECRET=your_secret_here

# AI Services (Required)
OPENAI_API_KEY=sk-your_openai_key_here
DEEPGRAM_API_KEY=your_deepgram_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here

# Optional Services
MEM0_API_KEY=your_mem0_key_here
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token

# Application Settings
PORT=8000
LOG_LEVEL=INFO
DEBUG=false
```

#### Frontend Environment (`frontend/.env.local`)
```env
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
NEXT_PUBLIC_DEFAULT_ROOM=agent-room
```

### Application URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Usage

### Creating an Agent
1. Navigate to http://localhost:3000/build
2. Configure agent identity and mission
3. Adjust personality sliders
4. Select voice settings
5. Upload knowledge base (optional)
6. Click "Create Agent"

### Voice Interaction
1. Join agent room at http://localhost:3000/chat
2. Grant microphone permissions
3. Click microphone button to start talking
4. Agent responds with synthesized voice

## Architecture

### Tech Stack
- **Frontend**: Next.js 14, React 18, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, LangGraph, LiveKit Python SDK
- **AI Services**: OpenAI GPT-4, Deepgram STT, ElevenLabs TTS
- **Real-time**: LiveKit WebRTC for audio streaming
- **Memory**: Mem0 for persistent context

### Directory Structure
```
OneShotVoiceAgent/
├── frontend/          # Next.js application
│   ├── app/          # App Router pages
│   ├── components/   # React components
│   └── lib/          # Utilities and API client
├── backend/          # FastAPI application
│   ├── api/          # API endpoints
│   ├── agents/       # LangGraph agent system
│   ├── services/     # External service integrations
│   └── models/       # Data models
└── scripts/          # Setup and deployment scripts
```

## Troubleshooting

### Common Issues

**Backend won't start**
- Verify Python 3.11+ installed: `python --version`
- Check virtual environment activated: `which python` should show `.venv`
- Validate environment variables in `backend/.env`

**Frontend build fails**
- Verify Node.js 18+ installed: `node --version`
- Clear Next.js cache: `rm -rf frontend/.next`
- Reinstall dependencies: `npm install --force`

**LiveKit connection fails**
- Check LIVEKIT_URL is WebSocket (starts with `wss://`)
- Verify API key and secret are correct
- Test connection: http://localhost:8000/health

**Voice not working**
- Grant microphone permissions in browser
- Check Deepgram API key is valid
- Verify ElevenLabs API key and voice ID

### Support
- Check logs in `backend/logs/` directory
- Enable debug mode: set `DEBUG=true` in backend/.env
- Test API endpoints: http://localhost:8000/docs