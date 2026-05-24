import asyncio
import dotenv
dotenv.load_dotenv() # Load env vars from .env file

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

async def main():
    print("Initializing agents...")
    agent_b = Agent(
        name="BillingAgent",
        instruction="You are a billing agent. Help with refunds, payments, and invoices.",
    )
    
    agent_a = Agent(
        name="FrontDeskAgent",
        instruction="You are a front desk agent. Welcome the user. Transfer to BillingAgent if they want to pay or get a refund.",
        sub_agents=[agent_b],
    )
    
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="travel_app",
        agent=agent_a,
        session_service=session_service,
        auto_create_session=True,
    )
    
    print("Running turn...")
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="Hi, I want a refund please.")]
    )
    
    async for event in runner.run_async(
        user_id="user_123",
        session_id="session_456",
        new_message=new_message,
    ):
        print("Event type:", type(event))
        print("Event content:", event)

if __name__ == "__main__":
    asyncio.run(main())
