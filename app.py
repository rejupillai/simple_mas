import os
import asyncio
import json
import sys

# Set a higher recursion limit for deep multi-agent runs
sys.setrecursionlimit(5000)

import logging
import dotenv
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables
dotenv.load_dotenv()

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aura_swarm")

# Ensure required env variables are present for Vertex AI or print warning
if not os.getenv("GOOGLE_GENAI_USE_VERTEXAI"):
    logger.warning("GOOGLE_GENAI_USE_VERTEXAI is not set. Defaulting to standard Gemini API.")

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

app = FastAPI(title="Aura Luxury Resort Swarm")

# ----------------------------------------------------------------------
# 1. Mock Database / Volatile State Layer
# ----------------------------------------------------------------------

INITIAL_BOOKINGS = {
    "booking_404": {
        "guest_name": "Bruce Wayne",
        "suite": "Presidential Penthouse",
        "check_in": "2026-06-01",
        "check_out": "2026-06-08",
        "balance": 17500.0,
        "amenities": ["Chilled Dom Pérignon on arrival", "Silk sheets"],
        "late_checkout": None
    },
    "booking_707": {
        "guest_name": "Selina Kyle",
        "suite": "Royal Ocean Villa",
        "check_in": "2026-05-28",
        "check_out": "2026-06-02",
        "balance": 9000.0,
        "amenities": ["Fresh white roses in master bath"],
        "late_checkout": None
    },
    "booking_101": {
        "guest_name": "Tony Stark",
        "suite": "Iron Pavilion Suite",
        "check_in": "2026-05-24",
        "check_out": "2026-05-29",
        "balance": 25000.0,
        "amenities": ["Organic blue berries", "Cold-pressed green juice"],
        "late_checkout": None
    }
}

INITIAL_SUITES = {
    "Presidential Penthouse": {
        "price_per_night": 2500.0,
        "available": True,
        "description": "Breathtaking 360-degree views, private heated infinity pool, and dedicated 24/7 butler service."
    },
    "Royal Ocean Villa": {
        "price_per_night": 1800.0,
        "available": True,
        "description": "Direct beach access, custom sunken ocean-view lounge, and glass floors looking into coral reef garden."
    },
    "Iron Pavilion Suite": {
        "price_per_night": 5000.0,
        "available": False,
        "description": "Smart penthouse with voice-controlled sensory pods, private helipad, and stunning mountain range vistas."
    },
    "Serenity Garden Suite": {
        "price_per_night": 1200.0,
        "available": True,
        "description": "Zen courtyards, natural flowing outdoor hot spring bath, and hand-woven silk sleeping pavilion."
    }
}

# State stores reset on demand
bookings = dict(INITIAL_BOOKINGS)
suites = dict(INITIAL_SUITES)
dining_reservations = []
spa_bookings = []
yacht_charters = []
helicopter_tours = []
audit_logs = []

def add_audit_log(agent: str, event_type: str, detail: str):
    log_entry = {
        "agent": agent,
        "event_type": event_type,
        "detail": detail,
        "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
    }
    audit_logs.append(log_entry)
    logger.info(f"[{agent}] {event_type}: {detail}")

# ----------------------------------------------------------------------
# 2. Tool Implementations with Robust Docstrings
# ----------------------------------------------------------------------

def check_suite_availability(check_in: str, check_out: str, suite_type: str) -> str:
    """Checks the availability and pricing of a specific luxury suite type at Aura Resort.

    Args:
        check_in: Starting date of stay in YYYY-MM-DD format (e.g. "2026-06-01").
        check_out: Ending date of stay in YYYY-MM-DD format (e.g. "2026-06-08").
        suite_type: The suite tier requested (e.g. "Presidential Penthouse", "Royal Ocean Villa", "Serenity Garden Suite").
    """
    add_audit_log("SuiteBooking", "TOOL_CALL", f"check_suite_availability: {suite_type} from {check_in} to {check_out}")
    if suite_type not in suites:
        available_list = ", ".join(suites.keys())
        return f"Error: Suite type '{suite_type}' does not exist. Available tiers: {available_list}."
    
    suite_info = suites[suite_type]
    if not suite_info["available"]:
        return f"The '{suite_type}' is currently booked for the requested period. We do have availability in our 'Royal Ocean Villa' or 'Serenity Garden Suite'."
    
    import datetime
    try:
        d1 = datetime.datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(check_out, "%Y-%m-%d")
        nights = (d2 - d1).days
        if nights <= 0:
            return "Error: Check-out date must be after check-in date."
        total_cost = nights * suite_info["price_per_night"]
        return (
            f"Yes, the exclusive '{suite_type}' is AVAILABLE for those dates. "
            f"Details: {suite_info['description']} "
            f"The rate is ${suite_info['price_per_night']:,} per night. "
            f"For a stay of {nights} nights, the total luxury package is ${total_cost:,}."
        )
    except Exception as e:
        return f"Error parsing dates. Please use YYYY-MM-DD. Error: {str(e)}"


def calculate_upgrade_cost(current_booking_id: str, target_suite: str) -> str:
    """Calculates the additional luxury package cost required to upgrade a guest's existing suite.

    Args:
        current_booking_id: The unique luxury booking ID of the guest (e.g., "booking_404").
        target_suite: The suite category the guest wishes to upgrade to (e.g., "Presidential Penthouse").
    """
    add_audit_log("SuiteBooking", "TOOL_CALL", f"calculate_upgrade_cost: {current_booking_id} -> {target_suite}")
    if current_booking_id not in bookings:
        return f"Error: Guest booking ID '{current_booking_id}' was not found in our elite guest database."
    if target_suite not in suites:
        return f"Error: Luxury suite category '{target_suite}' does not exist."
    
    booking = bookings[current_booking_id]
    current_suite = booking["suite"]
    
    if current_suite == target_suite:
        return f"Guest is already occupying the spectacular '{current_suite}'."
    
    current_rate = suites.get(current_suite, {}).get("price_per_night", 1000.0)
    target_rate = suites[target_suite]["price_per_night"]
    
    if target_rate <= current_rate:
        return f"The target suite '{target_suite}' (${target_rate:,}/night) is priced lower or equal to current suite '{current_suite}' (${current_rate:,}/night). A complimentary downgrade or side-grade can be processed. Contact front-desk."
    
    # Calculate nights
    import datetime
    try:
        d1 = datetime.datetime.strptime(booking["check_in"], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(booking["check_out"], "%Y-%m-%d")
        nights = (d2 - d1).days
        upgrade_per_night = target_rate - current_rate
        total_upgrade = upgrade_per_night * nights
        return (
            f"Let me calculate that upgrade for you. Upgrading from the '{current_suite}' "
            f"to the breathtaking '{target_suite}' requires an additional ${upgrade_per_night:,.2f} per night. "
            f"For your {nights}-night stay, the total upgrade balance adjustment would be exactly ${total_upgrade:,.2f}."
        )
    except Exception as e:
        return f"Error calculating upgrade: {str(e)}"


def book_dining(restaurant: str, party_size: int, date: str, time: str) -> str:
    """Reserves an exclusive table at one of Aura Resort's fine dining establishments.

    Args:
        restaurant: Name of the fine dining venue (e.g. "L’Ambroisie at Aura" or "Aura Beach Lounge").
        party_size: Number of guests dining (e.g. 2).
        date: Reservation date in YYYY-MM-DD format (e.g. "2026-06-03").
        time: Reservation time in HH:MM format, 24-hour style preferred (e.g. "20:00").
    """
    add_audit_log("DiningAndSpa", "TOOL_CALL", f"book_dining: {restaurant} for {party_size} guests on {date} at {time}")
    if restaurant not in ["L’Ambroisie at Aura", "Aura Beach Lounge"]:
        return "Error: We only have reservations available at our signature venues: 'L’Ambroisie at Aura' (3 Michelin Stars) or 'Aura Beach Lounge'."
    
    res = {
        "restaurant": restaurant,
        "party_size": party_size,
        "date": date,
        "time": time
    }
    dining_reservations.append(res)
    return (
        f"Success! I have secured a prime reservation at the distinguished '{restaurant}' "
        f"for a party of {party_size} on {date} at {time}. A digital confirmation and "
        f"the Sommelier's curated pairing menu have been sent to your device."
    )


def schedule_spa_session(treatment: str, date: str, time: str) -> str:
    """Schedules a bespoke wellness or massage session at the Aura Serenity Spa.

    Args:
        treatment: Type of holistic treatment requested (e.g. "Volcanic Hot Stone Therapy" or "Ocean Dew Facial Massage").
        date: Appointment date in YYYY-MM-DD format (e.g. "2026-06-04").
        time: Appointment time in HH:MM format, 24-hour style preferred (e.g. "14:30").
    """
    add_audit_log("DiningAndSpa", "TOOL_CALL", f"schedule_spa_session: {treatment} on {date} at {time}")
    valid_treatments = ["Volcanic Hot Stone Therapy", "Ocean Dew Facial Massage"]
    if treatment not in valid_treatments:
        return f"Error: Treatment '{treatment}' is not recognized. Our premium sessions are: 'Volcanic Hot Stone Therapy' or 'Ocean Dew Facial Massage'."
    
    booking = {
        "treatment": treatment,
        "date": date,
        "time": time
    }
    spa_bookings.append(booking)
    price = 320 if treatment == "Volcanic Hot Stone Therapy" else 220
    return (
        f"Perfectly scheduled! Your bespoke wellness session for '{treatment}' "
        f"is confirmed for {date} at {time}. The spa suite is reserved for you. "
        f"A session charge of ${price} will be placed on your final billing statement."
    )


def reserve_yacht_charter(yacht_type: str, date: str, duration_hours: int) -> str:
    """Books a private luxury ocean yacht charter with a personal chef and water sports crew.

    Args:
        yacht_type: The vessel class (e.g., "Zephyr (72ft Luxury Catamaran)" or "Aura Elite (110ft Superyacht)").
        date: The charter reservation date in YYYY-MM-DD format.
        duration_hours: Number of charter hours required (minimum of 4 hours).
    """
    add_audit_log("VIPActivities", "TOOL_CALL", f"reserve_yacht_charter: {yacht_type} on {date} for {duration_hours}h")
    yacht_catalog = {
        "Zephyr (72ft Luxury Catamaran)": 650.0,
        "Aura Elite (110ft Superyacht)": 1500.0
    }
    if yacht_type not in yacht_catalog:
        avail = ", ".join([f"'{y}'" for k, y in enumerate(yacht_catalog.keys())])
        return f"Error: Vessel class '{yacht_type}' is invalid. Elite vessels: {avail}."
    
    if duration_hours < 4:
        return "Our ocean voyages require a minimum charter duration of 4 hours to clear the outer harbor reefs."
    
    hourly_rate = yacht_catalog[yacht_type]
    total_cost = hourly_rate * duration_hours
    charter = {
        "yacht_type": yacht_type,
        "date": date,
        "duration_hours": duration_hours,
        "total_cost": total_cost
    }
    yacht_charters.append(charter)
    return (
        f"Outstanding choice! Your luxury private charter of the '{yacht_type}' "
        f"is reserved for {date} for a duration of {duration_hours} hours. "
        f"Includes captain, water sports coordinator, five-star crew, and private chef. "
        f"Total luxury vessel fee: ${total_cost:,.2f}."
    )


def book_helicopter_tour(tour_name: str, guest_count: int, date: str) -> str:
    """Books a private scenic helicopter tour departing from the resort's rooftop landing pad.

    Args:
        tour_name: The flight flightpath name (e.g. "Sunset Caldera Flight" or "Island Peak Exploration").
        guest_count: Number of elite flying passengers (maximum capacity 4 per flight).
        date: Desired flight date in YYYY-MM-DD format.
    """
    add_audit_log("VIPActivities", "TOOL_CALL", f"book_helicopter_tour: {tour_name} on {date} for {guest_count} guests")
    tours = {
        "Sunset Caldera Flight": 1200.0,
        "Island Peak Exploration": 1800.0
    }
    if tour_name not in tours:
        return "Error: Tour must be 'Sunset Caldera Flight' (gorgeous volcanic sunset views) or 'Island Peak Exploration' (includes private alpine peak champagne landing)."
    if guest_count > 4:
        return "Our premium Airbus H130 helicopters hold a maximum of 4 passengers per custom charter for safety and comfort."
    
    price_per_flight = tours[tour_name]
    tour_booking = {
        "tour_name": tour_name,
        "guest_count": guest_count,
        "date": date,
        "cost": price_per_flight
    }
    helicopter_tours.append(tour_booking)
    return (
        f"Charter secured! Your private helicopter tour '{tour_name}' is confirmed "
        f"for a party of {guest_count} on {date}. The flight will depart from Aura's VIP "
        f"rooftop launchpad. Cost: ${price_per_flight:,.2f} charter fee."
    )


def get_billing_statement(booking_id: str) -> str:
    """Fetches the current outstanding balance and detailed statement itemization for a guest's stay.

    Args:
        booking_id: The guest's unique luxury booking ID (e.g., "booking_404").
    """
    add_audit_log("BillingAndCustom", "TOOL_CALL", f"get_billing_statement: {booking_id}")
    if booking_id not in bookings:
        return f"Error: Booking ID '{booking_id}' not found in our elite guest database."
    
    booking = bookings[booking_id]
    current_balance = booking["balance"]
    
    # Calculate nights and base cost
    import datetime
    try:
        d1 = datetime.datetime.strptime(booking["check_in"], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(booking["check_out"], "%Y-%m-%d")
        nights = (d2 - d1).days
        rate = suites.get(booking["suite"], {}).get("price_per_night", 0)
        base_cost = nights * rate
        
        # Build statement description
        statement = (
            f"=== Aura Luxury Resort Statement ===\n"
            f"Guest Name: {booking['guest_name']}\n"
            f"Suite Tier: {booking['suite']}\n"
            f"Check-In: {booking['check_in']} | Check-Out: {booking['check_out']} ({nights} nights)\n"
            f"------------------------------------\n"
            f"Base Suite Lodging: ${base_cost:,.2f} (${rate:,.2f}/night)\n"
        )
        
        # Add details of auxiliary services if any booked
        extras = 0.0
        # Check yacht charters booked for date
        for yacht in yacht_charters:
            statement += f"Yacht Charter ({yacht['yacht_type']}): ${yacht['total_cost']:,.2f}\n"
            extras += yacht["total_cost"]
            
        for heli in helicopter_tours:
            statement += f"Helicopter Tour ({heli['tour_name']}): ${heli['cost']:,.2f}\n"
            extras += heli["cost"]
            
        for spa in spa_bookings:
            price = 320 if spa["treatment"] == "Volcanic Hot Stone Therapy" else 220
            statement += f"Serenity Spa Treatment ({spa['treatment']}): ${price:,.2f}\n"
            extras += price
            
        # Update balance dynamically
        new_balance = base_cost + extras
        bookings[booking_id]["balance"] = new_balance
        
        statement += (
            f"------------------------------------\n"
            f"Lodging Base: ${base_cost:,.2f}\n"
            f"Incidentals & Custom Add-ons: ${extras:,.2f}\n"
            f"TOTAL OUTSTANDING BALANCE: ${new_balance:,.2f}\n"
            f"===================================="
        )
        return statement
    except Exception as e:
        return f"Error generating statement: {str(e)}"


def approve_late_checkout(booking_id: str, request_time: str) -> str:
    """Evaluates and approves/denies late check-out requests based on room cleaning schedules and guest loyalty status.

    Args:
        booking_id: The guest's unique luxury booking ID (e.g., "booking_404").
        request_time: The requested late check-out time in 24h format (e.g. "14:00" or "16:00").
    """
    add_audit_log("BillingAndCustom", "TOOL_CALL", f"approve_late_checkout: {booking_id} to {request_time}")
    if booking_id not in bookings:
        return f"Error: Booking ID '{booking_id}' not found."
    
    booking = bookings[booking_id]
    guest_name = booking["guest_name"]
    suite_type = booking["suite"]
    
    # Simple rule: If the requested time is 14:00 or earlier, we approve instantly as a VIP courtesy.
    # If later, we check housekeeping availability.
    try:
        hour = int(request_time.split(":")[0])
        if hour <= 14:
            bookings[booking_id]["late_checkout"] = request_time
            return f"Courteous approval! As an elite guest, your request for a late checkout at {request_time} has been APPROVED for suite '{suite_type}' with our compliments. No extra fees apply."
        elif hour <= 17:
            bookings[booking_id]["late_checkout"] = request_time
            # Place a $150 premium cleaning service charge
            bookings[booking_id]["balance"] += 150.0
            return f"Extended checkout APPROVED. We have adjusted cleaning schedules for suite '{suite_type}' to accommodate you until {request_time}. A nominal incidental service fee of $150.00 has been applied to your ledger."
        else:
            return f"Regrettably, we cannot extend checkout until {request_time} as a new VIP guest arrives in that suite tier at 18:00. We can gladly store your luggage securely and provide full Spa and Lounge access for the remainder of your afternoon."
    except Exception as e:
        return f"Error parsing checkout time. Please use HH:MM format. Error: {str(e)}"


def record_custom_amenity(booking_id: str, item: str, delivery_time: str) -> str:
    """Prepares and schedules premium personalized setup or in-room gifts inside the guest's luxury suite.

    Args:
        booking_id: The guest's unique luxury booking ID (e.g., "booking_404").
        item: The VIP perk or amenity requested (e.g. "Chilled bottle of Dom Pérignon", "Dozen premium white roses", "Silk eye-mask").
        delivery_time: The desired setup or delivery time in 24h HH:MM format (e.g. "19:00").
    """
    add_audit_log("BillingAndCustom", "TOOL_CALL", f"record_custom_amenity: {item} for {booking_id} at {delivery_time}")
    if booking_id not in bookings:
        return f"Error: Booking ID '{booking_id}' not found."
    
    booking = bookings[booking_id]
    bookings[booking_id]["amenities"].append(f"{item} (delivered at {delivery_time})")
    
    # Charge if high-end amenity
    charge = 0.0
    if "champagne" in item.lower() or "dom" in item.lower():
        charge = 450.0
    elif "roses" in item.lower() or "flowers" in item.lower():
        charge = 120.0
        
    bookings[booking_id]["balance"] += charge
    
    msg = f"Delightful! I have scheduled '{item}' to be arranged in suite '{booking['suite']}' at exactly {delivery_time}."
    if charge > 0:
        msg += f" An elite service charge of ${charge:,.2f} has been added to your resort statement."
    else:
        msg += " This has been processed as a complimentary resort perk."
    return msg


# ----------------------------------------------------------------------
# 3. Define Google ADK Agents
# ----------------------------------------------------------------------

# We declare the agents as global variables.
# We will resolve their sub-agents dynamically to avoid circular issues.

# Select gemini-3.5-flash as the model (Vertex AI handles it)
MODEL_ID = "gemini-2.5-flash"

SuiteBookingAgent = Agent(
    name="SuiteBooking",
    description="Elite reservations concierge who manages room bookings, room types, checking suite availability, and upgrade pricing.",
    model=MODEL_ID,
    instruction=(
        "You are the Suite Booking Specialist at Aura Resort. You are an expert on our premium suite catalogs "
        "and handle availability checking and suite upgrades. "
        "Keep your tone warm, sophisticated, and elite.\n\n"
        "Available Tools:\n"
        "- check_suite_availability: Check suite pricing/availability for dates.\n"
        "- calculate_upgrade_cost: Work out cost differences for upgrades.\n\n"
        "Guidelines:\n"
        "1. If a guest asks about booking dates, available suite types, or room upgrades, assist them fully using your tools.\n"
        "2. If the guest wants to look up their existing booking details, check outstanding balances, pay bills, schedule custom room setups (flowers, champagne), "
        "or request late check-outs, immediately hand off by calling `transfer_to_agent` with 'BillingAndCustom'.\n"
        "3. If they wish to book michelin restaurant tables or spa sessions, hand off to 'DiningAndSpa'.\n"
        "4. If they want to charter ocean yachts or book private scenic helicopter tours, hand off to 'VIPActivities'.\n"
        "5. If they have general queries about resort location, weather, general policies, or basic hotel FAQs, hand off to 'AuraTriage'. Do NOT hand off for simple greetings (such as 'hello', 'hi', or introductions) or when they are asking a request you can handle."
    ),
    tools=[check_suite_availability, calculate_upgrade_cost]
)

DiningAndSpaAgent = Agent(
    name="DiningAndSpa",
    description="Fine Dining and Wellness Concierge managing Michelin-starred dining tables and bespoke spa therapies.",
    model=MODEL_ID,
    instruction=(
        "You are the Dining & Wellness Concierge at Aura Resort. You curate exceptional dining reservations "
        "at L’Ambroisie (3 Michelin stars) or Aura Beach Lounge, and schedule holistic therapies at our world-class Spa.\n\n"
        "Available Tools:\n"
        "- book_dining: Table reservations.\n"
        "- schedule_spa_session: Spa/massage appointments.\n\n"
        "Guidelines:\n"
        "1. Recommend custom menus or therapies based on guest preferences and book them.\n"
        "2. If the guest asks to check availability of a NEW suite, book a room, or modify booking dates, hand off to 'SuiteBooking'. If they ask about their existing booking/reservation details, suite name, or check-in/out times, hand off to 'BillingAndCustom' so they can look it up.\n"
        "3. If they want to inspect their bill, process a payment, schedule champagne/roses, or get late check-out, "
        "hand off to 'BillingAndCustom'.\n"
        "4. If they wish to book helicopter flights or luxury yacht charters, hand off to 'VIPActivities'.\n"
        "5. If they ask about general resort FAQs, location, weather, or general policies, hand off to 'AuraTriage'. Do NOT hand off for simple greetings (such as 'hello', 'hi', or introductions) or when they are asking a request you can handle."
    ),
    tools=[book_dining, schedule_spa_session]
)

VIPActivitiesAgent = Agent(
    name="VIPActivities",
    description="Adventure and High-End Excursions Agent orchestrating private superyacht charters and scenic helicopter flights.",
    model=MODEL_ID,
    instruction=(
        "You are the VIP Activities Specialist at Aura Resort. You curate high-end ocean voyages and flight path charters "
        "for our elite clientele.\n\n"
        "Available Tools:\n"
        "- reserve_yacht_charter: Yacht catamaran or superyacht booking.\n"
        "- book_helicopter_tour: Rooftop helipad flights.\n\n"
        "Guidelines:\n"
        "1. Highlight capacity guidelines (yachts 12-25, helicopters max 4) and provide premium tour summaries.\n"
        "2. If they need to check outstanding bill accounts, record VIP in-room amenities, look up existing reservation/booking details, or ask for late check-out, "
        "hand off to 'BillingAndCustom'.\n"
        "3. If they want to upgrade their room category, check dates, or book suites, hand off to 'SuiteBooking'.\n"
        "4. If they are seeking fine dining or spa treatments, hand off to 'DiningAndSpa'.\n"
        "5. If they ask about general resort FAQs, location, weather, or general policies, hand off to 'AuraTriage'. Do NOT hand off for simple greetings (such as 'hello', 'hi', or introductions) or when they are asking a request you can handle."
    ),
    tools=[reserve_yacht_charter, book_helicopter_tour]
)

BillingAndCustomAgent = Agent(
    name="BillingAndCustom",
    description="Elite Guest Relations & Finance Officer. Handles late check-outs, itemized statements, and luxury room amenities.",
    model=MODEL_ID,
    instruction=(
        "You are the Billing & Special Requests representative at Aura Resort. You manage detailed resort statements, "
        "late check-outs, and scheduling luxury custom setups (roses, champagne, custom gifts) delivered directly to suites.\n\n"
        "Available Tools:\n"
        "- get_billing_statement: Print detailed invoice totals and itemizations.\n"
        "- approve_late_checkout: Evaluate checkout extensions.\n"
        "- record_custom_amenity: Schedule premium room gifts/setups.\n\n"
        "Guidelines:\n"
        "1. Help guests understand their bills. Realize that billing statements reflect dynamic adjustments from bookings, spa bookings, tours, and amenities.\n"
        "2. If the guest wants to check the price/availability of a NEW suite booking or modify booking dates, or explicitly request to UPGRADE their current suite to a different tier, hand off to 'SuiteBooking'. For questions about their existing suite name, current reservation details, base amenities, checkout time, or billing, assist them directly (use get_billing_statement to look up their booking details).\n"
        "3. For fine dining reservations or spa slots, hand off to 'DiningAndSpa'.\n"
        "4. For scenic flightpaths or yacht voyages, hand off to 'VIPActivities'.\n"
        "5. If they have general queries about resort location, weather, general policies, or basic hotel FAQs, hand off to 'AuraTriage'. Do NOT hand off for simple greetings (such as 'hello', 'hi', or introductions) or when they are asking a request you can handle."
    ),
    tools=[get_billing_statement, approve_late_checkout, record_custom_amenity]
)

AuraTriageAgent = Agent(
    name="AuraTriage",
    description="The Aura Welcome Lead. Greets guests, answers general resort FAQs, and directs specific tasks to specialist agents.",
    model=MODEL_ID,
    instruction=(
        "You are the primary Aura Welcome & Triage Agent at Aura Resort. "
        "Greet guests with extreme warmth, luxury, and prestige. Your primary job is to handle basic resort welcomes, "
        "general resort FAQs (location, climate, general amenities), and route specialized requests to the correct expert agent.\n\n"
        "Guidelines to Route requests (CALL the `transfer_to_agent` tool immediately):\n"
        "1. Room availability, date changes, or suite upgrading? Transfer to 'SuiteBooking'.\n"
        "2. Restaurant seats, fine dining, or spa massages? Transfer to 'DiningAndSpa'.\n"
        "3. Rooftop helicopter flights or private yacht rentals? Transfer to 'VIPActivities'.\n"
        "4. Resort bills, invoice lists, late checkouts, or in-room perks like placing champagne or flowers? Transfer to 'BillingAndCustom'.\n\n"
        "Never try to execute specialized reservations yourself; transfer control immediately to show the swarm handoff power."
    ),
    tools=[],
    sub_agents=[SuiteBookingAgent, DiningAndSpaAgent, VIPActivitiesAgent, BillingAndCustomAgent]
)

# ----------------------------------------------------------------------
# 4. Bind Decentralized Sub-agents
# ----------------------------------------------------------------------

# We configure sub-agents natively under the root agent AuraTriage.
# The Google ADK automatically propagates peer-to-peer and parent-to-sub-agent
# transfer targets to all sub-agents via parent_agent, completely eliminating cyclic references.

# Setup Runner
session_service = InMemorySessionService()
runner = Runner(
    app_name="aura_concierge_app",
    agent=AuraTriageAgent,
    session_service=session_service,
    auto_create_session=True,
)

# ----------------------------------------------------------------------
# 5. FastAPI Endpoints & Static Files
# ----------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Streams Google ADK events to the client in real-time as SSE."""
    session_id = request.session_id
    user_id = "default_guest"
    user_msg = request.message
    
    add_audit_log("User", "USER_INPUT", f"[{session_id}] -> {user_msg}")
    
    new_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_msg)]
    )
    
    async def sse_event_generator():
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_content,
            ):
                # Clean event details for frontend consumption
                serialized = {
                    "id": event.id,
                    "author": event.author or "unknown",
                    "invocation_id": event.invocation_id,
                    "timestamp": event.timestamp,
                    "transfer_to_agent": event.actions.transfer_to_agent if event.actions else None,
                    "text": "",
                    "function_calls": [],
                    "function_responses": [],
                    "tokens": None
                }
                
                # Check for content parts
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            serialized["text"] += part.text
                        if part.function_call:
                            serialized["function_calls"].append({
                                "id": part.function_call.id,
                                "name": part.function_call.name,
                                "args": part.function_call.args
                            })
                        if part.function_response:
                            serialized["function_responses"].append({
                                "id": part.function_response.id,
                                "name": part.function_response.name,
                                "response": part.function_response.response
                            })
                
                # Check usage metadata
                if event.usage_metadata:
                    serialized["tokens"] = {
                        "prompt": event.usage_metadata.prompt_token_count,
                        "candidates": event.usage_metadata.candidates_token_count,
                        "total": event.usage_metadata.total_token_count,
                        "thoughts": getattr(event.usage_metadata, "thoughts_token_count", 0)
                    }
                    
                # Write audit log for transfers or tools inside backend
                if serialized["transfer_to_agent"]:
                    add_audit_log(serialized["author"], "SWARM_HANDOFF", f"Handoff control -> {serialized['transfer_to_agent']}")
                if serialized["text"] and serialized["author"] != "user":
                    add_audit_log(serialized["author"], "MODEL_RESPONSE", f"Text: {serialized['text'][:60]}...")
                
                yield f"data: {json.dumps(serialized)}\n\n"
                
        except Exception as e:
            logger.exception("Error in run_async event stream")
            err_packet = {
                "author": "System",
                "text": f"Error inside Swarm execution path: {str(e)}",
                "error": True
            }
            yield f"data: {json.dumps(err_packet)}\n\n"
            
    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@app.get("/api/agents")
def get_agents():
    """Returns the details of the available swarm agents for UI rendering."""
    # Custom aesthetic configs for UI
    agent_ui_configs = {
        "AuraTriage": {
            "accent": "hsl(38, 92%, 50%)",  # Luxurious Gold
            "icon": "⚜️",
            "desc": "Primary Luxury Triage Lead"
        },
        "SuiteBooking": {
            "accent": "hsl(142, 70%, 45%)",  # Resort Green
            "icon": "🔑",
            "desc": "Resort Lodging & Room Specialist"
        },
        "DiningAndSpa": {
            "accent": "hsl(330, 80%, 65%)",  # Orchid Pink
            "icon": "🌸",
            "desc": "Culinary & Serenity Spa Concierge"
        },
        "VIPActivities": {
            "accent": "hsl(263, 80%, 60%)",  # Helicopter Purple
            "icon": "🚁",
            "desc": "Elite Ocean & Air Adventures"
        },
        "BillingAndCustom": {
            "accent": "hsl(199, 95%, 48%)",  # Neon Ocean Blue
            "icon": "💎",
            "desc": "Guest Accounts & Special Requests"
        }
    }
    
    ret_agents = []
    for agent in [AuraTriageAgent, SuiteBookingAgent, DiningAndSpaAgent, VIPActivitiesAgent, BillingAndCustomAgent]:
        ui = agent_ui_configs.get(agent.name, {"accent": "hsl(0, 0%, 50%)", "icon": "🤖", "desc": "Swarm Agent"})
        tools_list = []
        
        # Get custom tools name & arguments
        import inspect
        for tool_union in agent.tools:
            # Check if callable tool
            if callable(tool_union):
                sig = inspect.signature(tool_union)
                tools_list.append({
                    "name": tool_union.__name__,
                    "doc": tool_union.__doc__.split("\n")[0] if tool_union.__doc__ else "",
                    "args": str(sig)
                })
        
        # Also let them know transfer_to_agent is available
        tools_list.append({
            "name": "transfer_to_agent",
            "doc": "Transfers current guest control to another specialized swarm agent.",
            "args": "(agent_name: str)"
        })
        
        ret_agents.append({
            "name": agent.name,
            "description": agent.description,
            "instruction": agent.instruction,
            "accent": ui["accent"],
            "icon": ui["icon"],
            "title_desc": ui["desc"],
            "tools": tools_list
        })
    return ret_agents


@app.get("/api/state")
def get_state():
    """Returns the current volatile database state and live audit logs."""
    return {
        "bookings": bookings,
        "suites": suites,
        "dining_reservations": dining_reservations,
        "spa_bookings": spa_bookings,
        "yacht_charters": yacht_charters,
        "helicopter_tours": helicopter_tours,
        "audit_logs": audit_logs[-50:] # return last 50 logs
    }


@app.post("/api/reset")
def reset_state():
    """Resets the volatile mock database and clear conversation sessions."""
    global bookings, suites, dining_reservations, spa_bookings, yacht_charters, helicopter_tours, audit_logs
    bookings = dict(INITIAL_BOOKINGS)
    suites = dict(INITIAL_SUITES)
    dining_reservations.clear()
    spa_bookings.clear()
    yacht_charters.clear()
    helicopter_tours.clear()
    audit_logs.clear()
    
    # We clear session service completely
    session_service.sessions.clear()
    
    add_audit_log("System", "RESET", "Swarm environment and memory completely cleared.")
    return {"status": "success", "message": "All mock states and conversation history have been reset."}


# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def get_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9070, reload=True)
