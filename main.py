#!/usr/bin/env python3
import os
import sys
import time
import requests
import logging
from datetime import date, datetime, time as dtime, timedelta
from dotenv import load_dotenv
from requests.auth import HTTPDigestAuth
from astral import LocationInfo
from astral.sun import sun

# Load configuration
load_dotenv()

DEVICE_IP = os.getenv("DEVICE_IP", "192.168.3.8")
USERNAME = "admin"
PASSWORD = os.getenv("PASSWORD", "YOUR_PASSWORD")  # Replace with your actual password

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Constants
GET_STATUS_URL = f"http://{DEVICE_IP}/rpc/Shelly.GetStatus"
SET_SWITCH_URL = f"http://{DEVICE_IP}/rpc/Switch.Set"

# Location configuration for astral
city = LocationInfo(name="Ann Arbor", region="USA", timezone="America/Detroit", latitude=42.2807, longitude=-83.7430)

def get_current_state(auth):
    """Get the current ON/OFF state of the switch."""
    logging.debug("Getting current state of switch.")
    response = requests.post(
        GET_STATUS_URL,
        json={"id": 1, "method": "Shelly.GetStatus"},
        auth=auth,
        timeout=5
    )
    if response.status_code != 200:
        logging.error(f"Failed to get status: {response.status_code} {response.text}")
        sys.exit(1)

    status_data = response.json()
    logging.debug(f"Status response: {status_data}")
    try:
        switch_state = status_data["switch:0"]["output"]
        return switch_state
    except KeyError:
        logging.error(f"Unexpected response structure: {status_data}")
        sys.exit(1)

def set_switch_state(auth, state: bool):
    """Set the switch to the given state (True for ON, False for OFF)."""
    payload = {
        "id": 0,
        "on": state
    }
    logging.debug(f"Setting switch state to {'ON' if state else 'OFF'}. Payload: {payload}")
    response = requests.post(SET_SWITCH_URL, json=payload, auth=auth, timeout=5)
    if response.status_code != 200:
        logging.error(f"Failed to set switch state to {'ON' if state else 'OFF'}: {response.status_code} {response.text}")
        sys.exit(1)
    logging.info(f"Switch state set to {'ON' if state else 'OFF'} successfully.")

def turn_on(auth):
    """Turn the device on if it's not already on."""
    current = get_current_state(auth)
    if not current:
        logging.info("Device is currently OFF, turning it ON...")
        set_switch_state(auth, True)
    else:
        logging.info("Device is already ON. No action taken.")

def turn_off(auth):
    """Turn the device off if it's not already off."""
    current = get_current_state(auth)
    if current:
        logging.info("Device is currently ON, turning it OFF...")
        set_switch_state(auth, False)
    else:
        logging.info("Device is already OFF. No action taken.")

def should_be_on(now, sunset):
    """
    Determine if the lights should be on or off at a given time.
    Lights should be ON from sunset until midnight.
    Otherwise OFF.
    """
    midnight = datetime.combine(now.date(), dtime(0, 0, 0)).replace(tzinfo=now.tzinfo) + timedelta(days=1)
    # If current time is after sunset and before midnight
    return sunset <= now < midnight

def main():
    auth = HTTPDigestAuth(USERNAME, PASSWORD)

    # Compute today's sunrise and sunset
    s = sun(city.observer, date=date.today(), tzinfo=city.timezone)
    sunrise = s["sunrise"]
    sunset = s["sunset"]

    logging.info(f"Sunrise: {sunrise}")
    logging.info(f"Sunset: {sunset}")

    while True:
        now = datetime.now(sunset.tzinfo)
        # Determine desired state
        desired_on = should_be_on(now, sunset)

        current_state = get_current_state(auth)
        if desired_on and not current_state:
            # Need to turn on
            logging.info("It's past sunset but before midnight - turning lights ON.")
            set_switch_state(auth, True)
        elif not desired_on and current_state:
            # Need to turn off
            logging.info("It's before sunset or past midnight - turning lights OFF.")
            set_switch_state(auth, False)
        else:
            # State is correct
            logging.debug("Lights are already in the correct state. No action needed.")

        # Sleep for some time before checking again.
        # Adjust this interval as needed, e.g., every 60 seconds.
        time.sleep(60)

if __name__ == "__main__":
    main()
