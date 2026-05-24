import sys
import app

print("Checking agents and their sub-agents:")
agents = [
    app.AuraTriageAgent,
    app.SuiteBookingAgent,
    app.DiningAndSpaAgent,
    app.VIPActivitiesAgent,
    app.BillingAndCustomAgent
]

for agent in agents:
    print(f"\nAgent: {agent.name}")
    print(f"  sub_agents: {[a.name for a in getattr(agent, 'sub_agents', [])]}")
    parent = getattr(agent, "parent_agent", None)
    print(f"  parent_agent: {parent.name if parent else 'None'}")

print("\nCalling find_agent on AuraTriageAgent:")
try:
    target = app.AuraTriageAgent.find_agent("BillingAndCustom")
    print(f"  Successfully found agent 'BillingAndCustom': {target.name if target else 'None'}")
except Exception as e:
    print(f"  Error calling find_agent: {e}")
    import traceback
    traceback.print_exc()
