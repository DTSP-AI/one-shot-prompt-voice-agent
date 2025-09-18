# 🔒 Security Guidelines - OneShotVoiceAgent

## 🚨 CRITICAL: API Key Security

### DO NOT COMMIT SECRETS TO VERSION CONTROL
- ❌ **NEVER** commit `.env` files with real API keys
- ❌ **NEVER** hardcode API keys in source code
- ❌ **NEVER** share API keys in chat logs or documentation
- ❌ **NEVER** push API keys to public repositories

### ✅ PROPER SECRET MANAGEMENT

#### 1. Local Development:
```bash
# Copy example file
cp .env.example .env

# Edit with your real API keys (NEVER commit this file)
nano .env
```

#### 2. Production Deployment:
- Use Azure Key Vault / AWS Secrets Manager
- Set environment variables in hosting platform
- Rotate keys regularly (every 90 days)

#### 3. Required API Keys:
```
OPENAI_API_KEY=sk-proj-*         # OpenAI GPT API
LIVEKIT_API_KEY=*                # LiveKit real-time communication
LIVEKIT_API_SECRET=*             # LiveKit authentication
DEEPGRAM_API_KEY=*               # Speech-to-text
ELEVENLABS_API_KEY=*             # Text-to-speech
MEM0_API_KEY=*                   # Persistent memory (optional)
```

## 🛡️ Security Checklist

### Before Every Commit:
- [ ] No `.env` files in git staging
- [ ] No hardcoded API keys in code
- [ ] `.gitignore` includes all secret patterns
- [ ] Log outputs don't contain secrets

### Before Production:
- [ ] All API keys rotated from development
- [ ] Secrets stored in secure key management
- [ ] CORS origins properly configured
- [ ] Debug mode disabled
- [ ] Rate limiting enabled

### Regular Maintenance:
- [ ] Monthly API key rotation
- [ ] Security dependency updates
- [ ] Log file cleanup (no secret leakage)
- [ ] Access audit for team members

## 🚨 If Secrets Are Compromised:

1. **IMMEDIATE**: Rotate all API keys
2. **IMMEDIATE**: Revoke compromised keys
3. **URGENT**: Check billing for unauthorized usage
4. **URGENT**: Review git history for secret exposure
5. **FOLLOW-UP**: Implement additional security controls

## 📞 Emergency Contacts:
- OpenAI: https://platform.openai.com/account/api-keys
- LiveKit: https://cloud.livekit.io/settings/keys
- Deepgram: https://console.deepgram.com/project/*/api-keys
- ElevenLabs: https://elevenlabs.io/settings/api-keys