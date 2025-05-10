from network import WLAN
import machine
import time
import ubinascii
from mqtt import MQTTClient
from pycoproc_1 import Pycoproc
from L76GNSS import L76GNSS
from LIS2HH12 import LIS2HH12
import uos

# ======== CONFIGURATION Wi-Fi ==========
WIFI_SSID = "Thibaut A54"
WIFI_PASS = "Thib123456"

# ======== CONFIGURATION MQTT ==========
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_TOPIC = "traqueur-pycom-voiture/gps"
MQTT_CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode()

# ======== INITIALISATION GPS et accéléromètre ==========
pytrack = Pycoproc(Pycoproc.PYTRACK)  # Initialise PyTrack
gps = L76GNSS(pytrack, timeout=42, buffer=411)
accel = LIS2HH12()

# ======== ATTENTE DU MOUVEMENT ==========
print("⏳ En attente d'un mouvement...")
seuil_mouvement = 0.4  # Seuil de détection (peut être ajusté)

# Prendre une moyenne initiale sur plusieurs lectures
def get_accel_moyenne(n=5):
    somme_x, somme_y, somme_z = 0, 0, 0
    for _ in range(n):
        x, y, z = accel.acceleration()
        somme_x += x
        somme_y += y
        somme_z += z
        time.sleep(0.1)  # Pause pour éviter le bruit
    return somme_x / n, somme_y / n, somme_z / n

x_old, y_old, z_old = get_accel_moyenne()

while True:
    time.sleep(0.5)  # Pause pour limiter le bruit
    x_new, y_new, z_new = get_accel_moyenne()

    # Calcul de la variation absolue
    diff_x = abs(x_new - x_old)
    diff_y = abs(y_new - y_old)
    diff_z = abs(z_new - z_old)

    if diff_x > seuil_mouvement or diff_y > seuil_mouvement or diff_z > seuil_mouvement:
        print("🚀 Mouvement détecté, démarrage du programme !")
        break  # Sortie de la boucle et démarrage du programme

    # Mise à jour des valeurs
    x_old, y_old, z_old = x_new, y_new, z_new

# ======== CONNEXION WI-FI ==========
wlan = WLAN(mode=WLAN.STA)
wlan.connect(WIFI_SSID, auth=(WLAN.WPA2, WIFI_PASS))

print("Connexion au Wi-Fi...")
while not wlan.isconnected():
    time.sleep(1)
print("Wi-Fi connecté! IP:", wlan.ifconfig()[0])

# ======== CONNEXION MQTT ==========
def connect_mqtt():
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT)
    client.connect()
    print("Connecté au broker MQTT")
    return client

client = connect_mqtt()

# ======== FONCTION POUR OBTENIR LES COORDONNÉES ==========
def get_gps_coordinates():
    lat, lon = gps.coordinates(debug=True)
    if lat is None or lon is None:
        print("Aucune coordonnée GPS valide, génération de coordonnées aléatoires...")
        lat = round(48.0773 + (uos.urandom(1)[0] / 255 - 0.5) * 0.01, 6)
        lon = round(7.3709 + (uos.urandom(1)[0] / 255 - 0.5) * 0.01, 6)
    return lat, lon

# ======== ENVOI DES DONNÉES ==========
try:
    while True:
        latitude, longitude = get_gps_coordinates()

        # Génération du lien Google Maps
        maps_link = "https://www.google.com/maps?q={},{}".format(latitude, longitude)

        # Préparation du message MQTT en format JSON manuel
        mqtt_message = '{"latitude": ' + str(latitude) + ', "longitude": ' + str(longitude) + ', "google_maps_link": "' + maps_link + '"}'

        # Envoi MQTT
        client.publish(topic=MQTT_TOPIC, msg=mqtt_message)
        print("📡 MQTT envoyé :", mqtt_message)

        # Pause avant le prochain envoi
        time.sleep(10)

except KeyboardInterrupt:
    print("Déconnexion...")
    client.disconnect()
