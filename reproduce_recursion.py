import asyncio
import os
import sys
import traceback
import dotenv

dotenv.load_dotenv()

from app import AuraTriageAgent, runner
from google.genai import types

async def main():
    print("Starting reproduction of the recursion/infinite-loop issue...")
    
    session_id = "REPRO_SESSION_123"
    user_id = "default_guest"
    user_msg = "Hi, I'm guest booking_404. I'd like to check my billing balance and order a chilled bottle of champagne."
    
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
            
            print(f"[{author}]: {text[:60]}...")
            if transfer:
                print(f"  ➔ Handoff Control: {author} -> {transfer}")
                
    except Exception as e:
        print("\n!!! EXCEPTION CAUGHT !!!")
        print(f"Error type: {type(e)}")
        print(f"Error message: {e}")
        
        # Walk up the traceback frames and inspect local variables of base_llm_flow.py or base_agent.py
        tb = e.__traceback__
        frames = []
        while tb is not None:
            frames.append(tb.tb_frame)
            tb = tb.tb_next
            
        print(f"Traceback depth: {len(frames)}")
        print("Last 15 frames:")
        for f in frames[-15:]:
            print(f"  File {f.f_code.co_filename}, line {f.f_lineno}, in {f.f_code.co_name}")
            # If find_agent or find_sub_agent, print self info
            if "base_agent.py" in f.f_code.co_filename:
                self_obj = f.f_locals.get("self")
                if self_obj:
                    name_param = f.f_locals.get("name")
                    print(f"    self={self_obj.name} (id={id(self_obj)}) searching for name={name_param}")
                    print(f"    self.sub_agents={[sa.name for a in getattr(self_obj, 'sub_agents', [])] if hasattr(self_obj, 'sub_agents') else 'N/A'}")
                    parent = getattr(self_obj, "parent_agent", None)
                    print(f"    self.parent_agent={parent.name if parent else 'None'}")

if __name__ == "__main__":
    asyncio.run(main())
