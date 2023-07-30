#Made by: gh0st
#Visit us @ IRC.TWISTEDNET.ORG CHANNELS: #TWISTED #DEV


import ssl
import irc.bot
import irc.connection
import time
import random
import sched
import json
import os
import threading
from jaraco.stream import buffer

class ZombieBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6697):
        irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
        factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname, connect_factory=factory)
        self.channel = channel
        self.zombies = {}
        self.scores = self.load_scores()
        self.bullets = {}  # Record the bullet count of each user
        self.scheduler = sched.scheduler(time.time, time.sleep)

    def is_connected(self):
        return self.connection.is_connected()

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        c.join(self.channel)
        self.start_scheduler()

    def start_scheduler(self):
        thread = threading.Thread(target=self.schedule_zombie_spawn, daemon=True)
        thread.start()

    def on_disconnect(self, c, e):
        time.sleep(5)
        self.jump_server()

    def schedule_zombie_spawn(self):
        while self.is_connected():
            self.spawn_zombie()
            time.sleep(random.randint(7200, 14400))

    def spawn_zombie(self):
        if self.is_connected():
            zombie_id = random.randint(1000, 9999)
            self.zombies[zombie_id] = time.time()
            self.send_message(f"A wild zombie (ID: {zombie_id}) appears! Type '!shoot {zombie_id}' to kill it!")

    def load_scores(self):
        if os.path.exists('zombies.json'):
            with open('zombies.json', 'r') as file:
                return json.load(file)
        else:
            return {}

    def save_scores(self):
        with open('zombies.json', 'w') as file:
            json.dump(self.scores, file)

    def on_pubmsg(self, c, e):
        message = e.arguments[0].strip()
        if message.startswith("!shoot"):
            self.handle_shooting(c, e)
        elif message.startswith("!reload"):
            self.handle_reloading(c, e)
        elif message.startswith("!scores"):
            self.print_scores()

    def handle_shooting(self, c, e):
        parts = e.arguments[0].split()
        if len(parts) != 2 or parts[0] != "!shoot":
            return

        user = e.source.nick
        if self.bullets.get(user, 0) <= 0:
            self.send_message(f"{user}, you're out of bullets! Use !reload to reload your gun.")
            return

        self.bullets[user] -= 1

        try:
            zombie_id = int(parts[1])
            if zombie_id in self.zombies:
                shot_time = time.time() - self.zombies[zombie_id]
                del self.zombies[zombie_id]
                self.scores[user] = self.scores.get(user, 0) + 1
                self.save_scores()
                self.send_message(f"Nice shot, {user}! You killed zombie {zombie_id} in {shot_time:.2f} seconds!")
            else:
                self.send_message(f"Zombie {zombie_id} is not found. Keep an eye on the channel for more zombies!")
        except ValueError:
            self.send_message("Invalid command format. Usage: !shoot <zombie_id>")

    def handle_reloading(self, c, e):
        user = e.source.nick
        self.bullets[user] = 4
        self.send_message(f"{user}, your gun is reloaded and ready to shoot!")

    def send_message(self, message):
        if self.is_connected():
            self.connection.privmsg(self.channel, message)

    def print_scores(self):
        if self.is_connected():
            if self.scores:
                self.send_message("Current Scores:")
                for user, score in self.scores.items():
                    self.send_message(f"{user}: {score}")
            else:
                self.send_message("No scores yet. Keep shooting zombies!")

def main():
    server = "irc.twistednet.org"
    channel = "#dev"
    nickname = "ZombieBot"

    bot = ZombieBot(channel, nickname, server)
    bot.start()

if __name__ == "__main__":
    main()
