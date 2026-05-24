import asyncio
import os
import sys
import dotenv

dotenv.load_dotenv()

from app import AuraTriageAgent, runner
from google.genai import types

async def main():
    print("Simulating multi-turn conversation in a single session...")
    session_id = "MULTI_TURN_SESSION_123"
    user_id = "default_guest"
    
    turns = [
        "Hi, I'm guest booking_404. I'd like to check my billing balance and order a chilled bottle of champagne.",
        "i want to book a yatch for 5hrs tomorrow"
    ]
    
    for i, user_msg in enumerate(turns):
        print(f"\n--- TURN {i+1}: {user_msg} ---")
        new_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_msg)]
        )
        
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_content,
            ):
                author = event.author or "unknown"
                transfer = event.actions.transfer_to_agent if event.actions else None
                text = ""
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            text += part.text
                
                if text:
                    print(f"[{author}]: {text[:60]}...")
                if transfer:
                    print(f"  ➔ Handoff Control: {author} -> {transfer}")
                    
        except Exception as e:
            print("\n!!! EXCEPTION CAUGHT !!!")
            print(f"Error type: {type(e)}")
            print(f"Error message: {e}")
            import traceback
            traceback.print_exc()
            break

if __name__ == "__main__":
    asyncio.run(main())
