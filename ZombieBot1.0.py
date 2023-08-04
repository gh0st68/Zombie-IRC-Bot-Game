#Made by: gh0st
#Visit us @ IRC.TWISTEDNET.ORG CHANNELS: #TWISTED #DEV

import ssl
import irc.bot
import irc.connection
import time
import random
import json
from jaraco.stream import buffer
import threading


class ZombieBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel_list, nickname, server, port=6697):
        irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer

        factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname, connect_factory=factory)
        self.channel_list = channel_list
        self.zombies = {channel.lower(): {} for channel in channel_list}
        self.explosion_chance = 0.05
        self.boss_chance = 0.90
        self.boss_health = 3
        self.scores = {}
        self.bullets = {}
        self.original_channels = channel_list.copy()

        try:
            with open("killz", "r") as f:
                data = json.load(f)
                self.scores = data.get('scores', {})
                self.bullets = data.get('bullets', {})
        except FileNotFoundError:
            pass

        self.channel_last_cleanup = {channel.lower(): 0 for channel in channel_list}

        self.is_running = False
        self.game_threads = []

    def is_connected(self):
        return self.connection.is_connected()

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        for channel in self.original_channels:
            c.join(channel)

        self.is_running = True
        for channel in self.channel_list:
            game_thread = threading.Thread(target=self.start_game_loop, args=(channel,))
            self.game_threads.append(game_thread)
            game_thread.start()

    def start_game_loop(self, channel):
        channel_lower = channel.lower()
        while self.is_connected() and self.is_running:
            current_time = time.time()
            if current_time - self.channel_last_cleanup[channel_lower] >= 600:
                self.cleanup_zombies(channel_lower)
                self.channel_last_cleanup[channel_lower] = current_time

            self.save_zombies_state()
            self.spawn_zombie(channel_lower)
            time.sleep(random.randint(1800, 3600))

    def on_pubmsg(self, c, e):
        message = e.arguments[0].strip()
        parts = message.split()
        if not parts:
            return

        command = parts[0].lower()

        if command == "!shoot":
            self.handle_shooting(c, e, parts)
        elif command == "!kills":
            self.print_scores(c, e)
        elif command == "!reload":
            self.handle_reloading(c, e)

    def on_disconnect(self, c, e):
        self.stop_game_loop()
        self.jump_server()

    def spawn_zombie(self, channel):
        if self.is_connected():
            zombie_id = random.randint(1000, 9999) ### SPAWN RATE
            if channel not in self.zombies:
                self.zombies[channel] = {}
            if random.random() < self.boss_chance:
                self.zombies[channel][zombie_id] = {"spawn_time": time.time(), "health": self.boss_health,
                                                    "is_boss": True}
                self.connection.privmsg(channel,
                                        f"A boss zombie (ID: {zombie_id}) appears! It takes {self.boss_health} bullets to kill. Type '!shoot {zombie_id}' to shoot it!")
            else:
                self.zombies[channel][zombie_id] = {"spawn_time": time.time(), "health": 1, "is_boss": False}
                self.connection.privmsg(channel,
                                        f"A wild zombie (ID: {zombie_id}) appears! Type '!shoot {zombie_id}' to kill it!")

    def handle_shooting(self, c, e, parts):
        user = e.source.nick
        channel = e.target

        if self.bullets.get(user) == "exploded":
            c.privmsg(channel, f"Oh no, {user}! Your gun exploded! Type '!reload' to repair your gun.")
            return

        if len(parts) != 2:
            c.privmsg(channel, f"Invalid command format. Usage: !shoot <zombie_id>")
            return

        try:
            zombie_id = int(parts[1])
            if user not in self.bullets or self.bullets[user] <= 0:
                c.privmsg(channel, f"{user}, you are out of bullets. Type '!reload' to reload your gun.")
                return

            self.bullets[user] -= 1

            if random.random() < self.explosion_chance:
                self.bullets[user] = "exploded"
                c.privmsg(channel, f"Oh no, {user}! Your gun exploded!")
                self.scores[user] = max(self.scores.get(user, 0) - 2, 0)
                c.privmsg(channel,
                          f"{user}, due to the gun explosion you've lost 2 kills. Your current score is now {self.scores[user]}")
                self.save_scores()
            else:
                channel_lower = channel.lower()
                if zombie_id in self.zombies.get(channel_lower, {}):
                    zombie = self.zombies[channel_lower][zombie_id]
                    if "health" in zombie:
                        if zombie["is_boss"]:
                            if zombie["health"] > 1:
                                zombie["health"] -= 1
                                c.privmsg(channel,
                                          f"Nice shot, {user}! You hit boss zombie {zombie_id}. It now has {zombie['health']} health left.")
                            else:
                                shot_time = time.time() - zombie["spawn_time"]
                                del self.zombies[channel_lower][zombie_id]
                                self.scores[user] = self.scores.get(user,
                                                                    0) + 2
                                c.privmsg(channel,
                                          f"Great job, {user}! You killed boss zombie {zombie_id} in {shot_time:.2f} seconds! You get 2 points! Your current score is now {self.scores[user]}.")
                                self.save_scores()
                        else:
                            shot_time = time.time() - zombie["spawn_time"]
                            del self.zombies[channel_lower][zombie_id]
                            self.scores[user] = self.scores.get(user, 0) + 1
                            c.privmsg(channel,
                                      f"Nice shot, {user}! You killed zombie {zombie_id} in {shot_time:.2f} seconds! Your current score is now {self.scores[user]}.")
                            self.save_scores()
                    else:
                        c.privmsg(channel,
                                  f"Zombie {zombie_id} is not found. Keep an eye on the channel for more zombies!")
                else:
                    c.privmsg(channel, f"Zombie {zombie_id} is not found. Keep an eye on the channel for more zombies!")

        except ValueError:
            c.privmsg(channel, "Invalid command format. Usage: !shoot <zombie_id>")

    def handle_reloading(self, c, e):
        user = e.source.nick
        channel = e.target
        self.bullets[user] = 5
        if self.bullets.get(user) == "exploded":
            c.privmsg(channel, f"{user}, your gun has been fixed and reloaded!")
        else:
            c.privmsg(channel, f"{user}, your gun is reloaded!")

    def print_scores(self, c, e):
        user = e.source.nick
        if self.is_connected():
            if self.scores:
                c.notice(user, "Current Scores:")
                for scorer, score in self.scores.items():
                    c.notice(user, f"{scorer}: {score}")
            else:
                c.notice(user, "No scores yet. Keep shooting zombies!")

    def save_scores(self):
        with open("killz", "w") as f:
            json.dump({'scores': self.scores, 'bullets': self.bullets}, f)

    def cleanup_zombies(self, channel):
        if channel not in self.zombies:
            print(f"Channel {channel} not found in zombies dictionary")
            return

        current_time = time.time()
        zombies = self.zombies[channel]
        zombies_to_remove = [zombie_id for zombie_id, zombie in zombies.items() if
                             current_time - zombie["spawn_time"] > 600]
        for zombie_id in zombies_to_remove:
            del zombies[zombie_id]

    def save_zombies_state(self):
        with open("zombies_state.json", "w") as f:
            json.dump(self.zombies, f)

    def load_zombies_state(self):
        try:
            with open("zombies_state.json", "r") as f:
                data = json.load(f)
                self.zombies = data
        except FileNotFoundError:
            pass

    def stop_game_loop(self):
        self.is_running = False
        for game_thread in self.game_threads:
            game_thread.join()

    def run(self):
        self.load_zombies_state()
        super().start()


def main():
    server = "irc.twistednet.org"
    channel_list = ["#Twisted", "#chat"]  
    nickname = "Zombie"

    bot = ZombieBot(channel_list, nickname, server)
    bot.run()


if __name__ == "__main__":
    main()
