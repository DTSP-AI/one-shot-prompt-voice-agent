#!/usr/bin/env python3

import requests
import json

def test_invoke_endpoint():
    url = "http://localhost:8000/api/v1/agent/invoke"
    
    payload = {
        "user_input": "Hello test",
        "session_id": "test-session-123", 
        "tenant_id": "default",
        "voice_id": "test-voice",
        "tts_enabled": False,
        "model": "gpt-4",
        "agent_id": "test-agent",
        "traits": {
            "name": "TestBot",
            "shortDescription": "Test assistant", 
            "identity": "I am an AI assistant",
            "mission": "To help users",
            "interactionStyle": "Friendly",
            "creativity": 75,
            "empathy": 80,
            "assertiveness": 60,
            "verbosity": 50,
            "formality": 40,
            "confidence": 70,
            "humor": 35,
            "technicality": 65,
            "safety": 90
        }
    }
    
    try:
        print("Sending request to:", url)
        print("Payload:", json.dumps(payload, indent=2))
        
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            try:
                json_response = response.json()
                print(f"JSON Response: {json.dumps(json_response, indent=2)}")
            except:
                print("Failed to parse JSON response")
                
    except requests.exceptions.Timeout:
        print("Request timed out after 30 seconds")
    except requests.exceptions.ConnectionError:
        print("Connection error - is the server running?")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_invoke_endpoint()
