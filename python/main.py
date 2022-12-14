from dotenv import dotenv_values
import requests
import webbrowser
import websocket
import json
from lib.math import normalize_heading
import time
import math

FRONTEND_BASE = "noflight.monad.fi"
BACKEND_BASE = "noflight.monad.fi/backend"
game_id = None
locked1 = False
circulating1 = False
locked2 = False
circulating2 = False


def on_message(ws: websocket.WebSocketApp, message):
    [action, payload] = json.loads(message)

    if action != "game-instance":
        print([action, payload])
        return

    # New game tick arrived!
    game_state = json.loads(payload["gameState"])
    commands = generate_commands(game_state)

    time.sleep(0.1)
    ws.send(json.dumps(["run-command", {"gameId": game_id, "payload": commands}]))


def on_error(ws: websocket.WebSocketApp, error):
    print(error)


def on_open(ws: websocket.WebSocketApp):
    print("OPENED")
    ws.send(json.dumps(["sub-game", {"id": game_id}]))


def on_close(ws, close_status_code, close_msg):
    print("CLOSED")


# Change this to your own implementation


def generate_commands(game_state):
    commands = []
    #radius is turning radius of the aircraft when max rotation (20 degrees)
    radius = 12
    #epsilon is used to prevent tiny adjustments to direction
    epsilon = 3
    global locked1
    global circulating1
    global locked2
    global circulating2

    locked = None
    circulating = None
    clockwise = True

    for aircraft in game_state["aircrafts"]:
        # TODO SPAGHETTI CODE SOLUTION: Maybe data structure for booleans?
        # also global variables aren't the best way to go.
        if aircraft["id"] == "1":
            locked = locked1
            circulating = circulating1
        else:
            locked = locked2
            circulating = circulating2

        destination_airport = None
        destination_airport_name = aircraft["destination"]

        # find matching airport
        for airport in game_state["airports"]:
            if airport["name"] == destination_airport_name:
                destination_airport = airport
        steer = 0

        ac_dir = aircraft["direction"]
        ap_dir = destination_airport["direction"]
        degree = aircraft["direction"] - destination_airport["direction"]
        d_x = destination_airport["position"]["x"] - aircraft["position"]["x"]
        d_y = destination_airport["position"]["y"] - aircraft["position"]["y"]

        # if aircrafts position and directions is close enough, set direction to same as airport to land
        dist = math.sqrt(math.pow(d_x, 2) + math.pow(d_y, 2))
        if dist <= 10 and abs(destination_airport["direction"] - aircraft["direction"]) <= 20:
            new_dir = normalize_heading(destination_airport['direction'])
            commands.append(f"HEAD {aircraft['id']} {new_dir}")
            print("landed")
            # TODO
            continue

        circle_center_x = None
        circle_center_y = None
        distance_to_circle_center = None
        delta_x_to_circle_center = None
        delta_y_to_circle_center = None

        # TODO:  CHECK WHICH SIDE THE PLANE IS RELATED TO AIRPORT
        # estimate which side of tangent normal "circle" should be drawn
        # this is for possible future use
        # "negative" side
        circle_center_x_positive = destination_airport["position"]["x"] + math.cos(
            math.radians(destination_airport["direction"] - 90)) * radius
        circle_center_y_positive = destination_airport["position"]["y"] + math.sin(
            math.radians(destination_airport["direction"] - 90)) * radius
        delta_x_to_circle_center_positive = circle_center_x_positive - aircraft["position"]["x"]
        delta_y_to_circle_center_positive = circle_center_y_positive - aircraft["position"]["y"]
        distance_to_circle_center_positive = math.sqrt(
            math.pow(delta_x_to_circle_center_positive, 2) + math.pow(delta_y_to_circle_center_positive, 2))

        # "positive" side, to work -90 must be changed to +90
        circle_center_x_negative = destination_airport["position"]["x"] + math.cos(
            math.radians(destination_airport["direction"] - 90)) * radius
        circle_center_y_negative = destination_airport["position"]["y"] + math.sin(
            math.radians(destination_airport["direction"] - 90)) * radius
        delta_x_to_circle_center_negative = circle_center_x_negative - aircraft["position"]["x"]
        delta_y_to_circle_center_negative = circle_center_y_negative - aircraft["position"]["y"]
        distance_to_circle_center_negative = math.sqrt(
            math.pow(delta_x_to_circle_center_negative, 2) + math.pow(delta_y_to_circle_center_negative, 2))


        if distance_to_circle_center_negative < distance_to_circle_center_positive:
            circle_center_x = circle_center_x_negative
            circle_center_y = circle_center_y_negative
            distance_to_circle_center = distance_to_circle_center_negative
            delta_x_to_circle_center = delta_x_to_circle_center_negative
            delta_y_to_circle_center = delta_y_to_circle_center_negative
        else:
            circle_center_x = circle_center_x_positive
            circle_center_y = circle_center_y_positive
            distance_to_circle_center = distance_to_circle_center_positive
            delta_x_to_circle_center = delta_x_to_circle_center_positive
            delta_y_to_circle_center = delta_y_to_circle_center_positive


        # TODO CHOOSE THE SIDE OF THE AIRCRAFT
        #declaration for all 3 angles that are used to calc aircrafts direction
        alpha = 0
        beta = 0
        gamma = None
        try:
            beta = math.degrees(math.asin(radius / distance_to_circle_center))
        except:
            print("Something went wrong")

        gamma = math.degrees(math.atan(delta_y_to_circle_center / delta_x_to_circle_center))

        # unit circle: get all angles right
        if delta_x_to_circle_center >= 0:
            # 0-90 degrees
            if delta_y_to_circle_center >= 0:
                alpha = beta + gamma
                #TODO
                if not clockwise:
                    pass
                    #alpha =gamma-beta
            # TODO270-360 degrees
            else:
                pass
        else:
            # 90-180 degrees
            if delta_y_to_circle_center >= 0:
                # TODO
                pass
            # 180-270 degrees
            else:
                gamma = math.degrees(math.atan(abs(delta_x_to_circle_center) / abs(delta_y_to_circle_center)))
                alpha = 270 - gamma + beta

        if circulating:
            steer = 20
            new_dir = normalize_heading(aircraft['direction'] - steer)
            commands.append(f"HEAD {aircraft['id']} {new_dir}")
            continue

        if locked:
            if distance_to_circle_center <= radius:
                if aircraft["id"] == "1":
                    print("id1")
                    circulating1 = True
                else:
                    print("id2")
                    circulating2 = True
                circulating =True
            continue

        if abs(alpha - aircraft["direction"]) >= epsilon:
            steer = 0
            #if is possible turn as hard as possible
            if abs(aircraft["direction"] - alpha) >= 20:
                print(">20")
                #decide which side to turn
                if aircraft["direction"] -alpha >= 0:
                    steer=20
                else:
                    steer = -20
                #steer = 20
            #for turns smaller than 20 degrees
            else:
                steer = aircraft["direction"] - alpha
            new_dir = normalize_heading(aircraft['direction'] - steer)
            commands.append(f"HEAD {aircraft['id']} {new_dir}")
            continue
        else:
            if aircraft["id"] == "1":
                locked1 = True
            else:
                locked2 = True
    return commands

def main():
    config = dotenv_values()
    res = requests.post(
        f"https://{BACKEND_BASE}/api/levels/{config['LEVEL_ID']}",
        headers={
            "Authorization": config["TOKEN"]
        })

    if not res.ok:
        print(f"Couldn't create game: {res.status_code} - {res.text}")
        return

    game_instance = res.json()

    global game_id
    game_id = game_instance["entityId"]

    url = f"https://{FRONTEND_BASE}/?id={game_id}"
    print(f"Game at {url}")
    webbrowser.open(url, new=2)
    time.sleep(2)

    ws = websocket.WebSocketApp(
        f"wss://{BACKEND_BASE}/{config['TOKEN']}/", on_message=on_message, on_open=on_open, on_close=on_close,
        on_error=on_error)
    ws.run_forever()


if __name__ == "__main__":
    main()
