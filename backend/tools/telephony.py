"""
Telephony integration with LiveKit SIP Ingress and Twilio bridge fallback.
Handles phone call routing and PSTN connectivity.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import re

try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

import httpx

logger = logging.getLogger(__name__)


class TelephonyError(Exception):
    """Custom telephony error with remediation suggestions."""
    
    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class SIPIngressManager:
    """Manages LiveKit SIP Ingress connections."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ingress_url = config.get("LIVEKIT_SIP_INGRESS_URL")
        self.ingress_auth = config.get("LIVEKIT_SIP_INGRESS_AUTH")
        
        # Parse SIP URL
        if self.ingress_url:
            self.parsed_sip = self._parse_sip_url(self.ingress_url)
        else:
            self.parsed_sip = None
        
        self.active_calls: Dict[str, Dict[str, Any]] = {}
    
    def _parse_sip_url(self, sip_url: str) -> Optional[Dict[str, str]]:
        """Parse SIP URL into components."""
        try:
            # Match pattern: sip:ingress-id@host:port
            pattern = r'sip:([^@]+)@([^:]+)(?::(\d+))?'
            match = re.match(pattern, sip_url)
            
            if match:
                return {
                    "ingress_id": match.group(1),
                    "host": match.group(2),
                    "port": match.group(3) or "5060"
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse SIP URL: {e}")
            return None
    
    async def create_ingress(self, 
                           name: str,
                           room_name: str,
                           participant_identity: Optional[str] = None) -> Dict[str, Any]:
        """Create SIP ingress for incoming calls."""
        try:
            if not self.parsed_sip:
                raise TelephonyError(
                    "SIP ingress not configured",
                    "Set LIVEKIT_SIP_INGRESS_URL in environment"
                )
            
            # This would typically use LiveKit's SIP API
            # For now, return mock configuration
            ingress_config = {
                "ingress_id": f"sip_{name}_{datetime.now().timestamp()}",
                "sip_uri": f"sip:{self.parsed_sip['ingress_id']}@{self.parsed_sip['host']}",
                "room_name": room_name,
                "participant_identity": participant_identity or f"phone_{name}",
                "created_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
            
            logger.info(f"Created SIP ingress: {ingress_config['ingress_id']}")
            return ingress_config
            
        except Exception as e:
            logger.error(f"Failed to create SIP ingress: {e}")
            raise TelephonyError(
                f"SIP ingress creation failed: {e}",
                "Check LiveKit SIP configuration and permissions"
            )
    
    async def handle_incoming_call(self, 
                                  call_data: Dict[str, Any],
                                  callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Handle incoming SIP call."""
        try:
            call_id = call_data.get("call_id", f"call_{datetime.now().timestamp()}")
            caller_number = call_data.get("from", "unknown")
            
            call_info = {
                "call_id": call_id,
                "caller_number": caller_number,
                "start_time": datetime.utcnow(),
                "status": "ringing",
                "ingress_id": call_data.get("ingress_id"),
                "room_name": call_data.get("room_name")
            }
            
            self.active_calls[call_id] = call_info
            
            logger.info(f"Incoming call from {caller_number}: {call_id}")
            
            if callback:
                await callback(call_info)
            
            return call_info
            
        except Exception as e:
            logger.error(f"Failed to handle incoming call: {e}")
            raise TelephonyError(
                f"Call handling failed: {e}",
                "Check SIP ingress configuration"
            )
    
    async def end_call(self, call_id: str) -> bool:
        """End active SIP call."""
        try:
            if call_id in self.active_calls:
                call_info = self.active_calls[call_id]
                call_info["status"] = "ended"
                call_info["end_time"] = datetime.utcnow()
                
                # Calculate call duration
                start_time = call_info["start_time"]
                end_time = call_info["end_time"]
                duration = (end_time - start_time).total_seconds()
                call_info["duration_seconds"] = duration
                
                logger.info(f"Call ended: {call_id} (duration: {duration}s)")
                del self.active_calls[call_id]
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return False
    
    def get_active_calls(self) -> Dict[str, Dict[str, Any]]:
        """Get list of active calls."""
        return self.active_calls.copy()


class TwilioBridge:
    """Twilio bridge for PSTN connectivity fallback."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.account_sid = config.get("TWILIO_ACCOUNT_SID")
        self.auth_token = config.get("TWILIO_AUTH_TOKEN")
        self.from_number = config.get("TWILIO_FROM_NUMBER")
        self.ingress_uri = config.get("TWILIO_INGRESS_SIP_URI")
        
        if TWILIO_AVAILABLE and self.account_sid and self.auth_token:
            self.client = TwilioClient(self.account_sid, self.auth_token)
            self.available = True
        else:
            self.client = None
            self.available = False
            logger.warning("Twilio not configured or unavailable")
        
        self.active_calls: Dict[str, Dict[str, Any]] = {}
    
    async def make_call(self, 
                       to_number: str,
                       message: str = "Hello from the AI agent",
                       callback_url: Optional[str] = None) -> Dict[str, Any]:
        """Make outbound call via Twilio."""
        if not self.available:
            raise TelephonyError(
                "Twilio not available",
                "Configure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"
            )
        
        try:
            # Create TwiML for the call
            twiml = f"""
            <Response>
                <Say voice="alice">{message}</Say>
                <Dial>
                    <Sip>{self.ingress_uri}</Sip>
                </Dial>
            </Response>
            """
            
            call = self.client.calls.create(
                to=to_number,
                from_=self.from_number,
                twiml=twiml,
                status_callback=callback_url,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                record=True
            )
            
            call_info = {
                "call_sid": call.sid,
                "to_number": to_number,
                "from_number": self.from_number,
                "status": call.status,
                "start_time": datetime.utcnow(),
                "direction": "outbound"
            }
            
            self.active_calls[call.sid] = call_info
            
            logger.info(f"Outbound call initiated: {call.sid} to {to_number}")
            return call_info
            
        except TwilioException as e:
            logger.error(f"Twilio call failed: {e}")
            raise TelephonyError(
                f"Outbound call failed: {e}",
                "Check Twilio account balance and phone number verification"
            )
    
    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Twilio webhook events."""
        try:
            call_sid = webhook_data.get("CallSid")
            call_status = webhook_data.get("CallStatus")
            
            if call_sid in self.active_calls:
                self.active_calls[call_sid]["status"] = call_status
                
                if call_status in ["completed", "busy", "failed", "no-answer"]:
                    call_info = self.active_calls[call_sid]
                    call_info["end_time"] = datetime.utcnow()
                    
                    # Calculate duration if available
                    if "CallDuration" in webhook_data:
                        call_info["duration_seconds"] = int(webhook_data["CallDuration"])
                    
                    logger.info(f"Call completed: {call_sid} with status {call_status}")
                    del self.active_calls[call_sid]
            
            return {
                "call_sid": call_sid,
                "status": call_status,
                "processed": True
            }
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return {
                "error": str(e),
                "processed": False
            }
    
    async def get_call_recordings(self, call_sid: str) -> List[Dict[str, Any]]:
        """Get recordings for a call."""
        if not self.available:
            return []
        
        try:
            recordings = self.client.recordings.list(call_sid=call_sid)
            
            return [
                {
                    "sid": recording.sid,
                    "duration": recording.duration,
                    "date_created": recording.date_created.isoformat(),
                    "uri": recording.uri,
                    "media_url": f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                }
                for recording in recordings
            ]
            
        except TwilioException as e:
            logger.error(f"Failed to get recordings: {e}")
            return []


class TelephonyManager:
    """Main telephony manager coordinating SIP and Twilio."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("ENABLE_TELEPHONY", False)
        self.mode = config.get("TELEPHONY_MODE", "sip_ingress")  # sip_ingress | twilio
        
        # Initialize components
        self.sip_manager = SIPIngressManager(config) if self.mode == "sip_ingress" else None
        self.twilio_bridge = TwilioBridge(config) if TWILIO_AVAILABLE else None
        
        # Call tracking
        self.total_calls = 0
        self.active_calls_count = 0
        self.call_history: List[Dict[str, Any]] = []
        
        if not self.enabled:
            logger.info("Telephony disabled")
    
    async def handle_incoming_call(self, 
                                  call_data: Dict[str, Any],
                                  callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Handle incoming call based on configured mode."""
        if not self.enabled:
            raise TelephonyError(
                "Telephony disabled",
                "Set ENABLE_TELEPHONY=true to enable phone calls"
            )
        
        self.total_calls += 1
        self.active_calls_count += 1
        
        try:
            if self.mode == "sip_ingress" and self.sip_manager:
                result = await self.sip_manager.handle_incoming_call(call_data, callback)
            else:
                # Fallback handling
                result = {
                    "call_id": f"fallback_{datetime.now().timestamp()}",
                    "status": "handled_fallback",
                    "message": "Telephony fallback mode"
                }
            
            # Add to call history
            self.call_history.append({
                **result,
                "timestamp": datetime.utcnow().isoformat(),
                "direction": "inbound"
            })
            
            return result
            
        except Exception as e:
            self.active_calls_count -= 1
            logger.error(f"Call handling failed: {e}")
            raise
    
    async def make_outbound_call(self, 
                               to_number: str,
                               message: str = "Hello from AI agent") -> Dict[str, Any]:
        """Make outbound call using available service."""
        if not self.enabled:
            raise TelephonyError(
                "Telephony disabled",
                "Set ENABLE_TELEPHONY=true to enable phone calls"
            )
        
        if not self.twilio_bridge or not self.twilio_bridge.available:
            raise TelephonyError(
                "Outbound calls not available",
                "Configure Twilio for outbound calling"
            )
        
        self.total_calls += 1
        self.active_calls_count += 1
        
        try:
            result = await self.twilio_bridge.make_call(to_number, message)
            
            # Add to call history
            self.call_history.append({
                **result,
                "timestamp": datetime.utcnow().isoformat(),
                "direction": "outbound"
            })
            
            return result
            
        except Exception as e:
            self.active_calls_count -= 1
            logger.error(f"Outbound call failed: {e}")
            raise
    
    async def end_call(self, call_id: str) -> bool:
        """End active call."""
        success = False
        
        if self.sip_manager:
            success = await self.sip_manager.end_call(call_id)
        
        if success:
            self.active_calls_count = max(0, self.active_calls_count - 1)
        
        return success
    
    def get_call_stats(self) -> Dict[str, Any]:
        """Get telephony statistics."""
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "total_calls": self.total_calls,
            "active_calls": self.active_calls_count,
            "call_history_count": len(self.call_history),
            "sip_available": self.sip_manager is not None,
            "twilio_available": self.twilio_bridge.available if self.twilio_bridge else False
        }
    
    def get_active_calls(self) -> List[Dict[str, Any]]:
        """Get list of all active calls."""
        active_calls = []
        
        if self.sip_manager:
            sip_calls = self.sip_manager.get_active_calls()
            active_calls.extend(list(sip_calls.values()))
        
        if self.twilio_bridge:
            twilio_calls = list(self.twilio_bridge.active_calls.values())
            active_calls.extend(twilio_calls)
        
        return active_calls
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform telephony service health check."""
        try:
            status = {
                "enabled": self.enabled,
                "mode": self.mode,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not self.enabled:
                status["status"] = "disabled"
                return status
            
            # Check SIP ingress
            if self.sip_manager:
                sip_healthy = self.sip_manager.parsed_sip is not None
                status["sip_ingress"] = {
                    "configured": sip_healthy,
                    "active_calls": len(self.sip_manager.active_calls)
                }
            
            # Check Twilio
            if self.twilio_bridge:
                status["twilio"] = {
                    "available": self.twilio_bridge.available,
                    "active_calls": len(self.twilio_bridge.active_calls)
                }
                
                # Test Twilio connectivity if configured
                if self.twilio_bridge.available:
                    try:
                        # Simple account fetch test
                        account = self.twilio_bridge.client.api.accounts(self.twilio_bridge.account_sid).fetch()
                        status["twilio"]["account_status"] = account.status
                        status["twilio"]["healthy"] = True
                    except Exception as e:
                        status["twilio"]["healthy"] = False
                        status["twilio"]["error"] = str(e)
            
            # Overall status
            if self.mode == "sip_ingress":
                status["status"] = "healthy" if status.get("sip_ingress", {}).get("configured") else "unhealthy"
            elif self.mode == "twilio":
                status["status"] = "healthy" if status.get("twilio", {}).get("healthy") else "unhealthy"
            else:
                status["status"] = "unknown"
            
            return status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "enabled": self.enabled,
                "timestamp": datetime.utcnow().isoformat(),
                "remediation": "Check telephony service configuration"
            }