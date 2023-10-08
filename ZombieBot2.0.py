##For help or questions, bugs etc.. join #dev and #twisted on irc.twistednet.org
##Made by gh0st


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
        self.scores = {}
        self.bullets = {}
        self.original_channels = channel_list.copy()

        self.zombie_types = [
            {"name": "🧟 Radioactive Zombie", "health": 1, "points": 1},
            {"name": "🧟 Cryptkeeper Zombie", "health": 1, "points": 2},
            {"name": "🧟 Voodoo Priest Zombie", "health": 2, "points": 3},
            {"name": "🧟 Creepy Crawler Zombie", "health": 2, "points": 4}
        ]

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
            time_interval = random.randint(5400, 9000)
            time.sleep(time_interval)

    def on_pubmsg(self, c, e):
        message = e.arguments[0].strip()
        parts = message.split()
        if not parts:
            return

        command = parts[0].lower()

        if command == ".shoot":
            self.handle_shooting(c, e, parts)
        elif command == ".kills":
            self.print_scores(c, e)
        elif command == ".reload":
            self.handle_reloading(c, e)

    def on_disconnect(self, c, e):
        self.stop_game_loop()
        self.jump_server()

    def spawn_zombie(self, channel):
        if self.is_connected():
            zombie_id = str(random.randint(10, 99))
            zombie_props = random.choice(self.zombie_types)

            zombie_name = zombie_props["name"]
            zombie_health = zombie_props["health"]
            zombie_points = zombie_props.get("points", 0)

            print(f"Spawning {zombie_name} (ID: {zombie_id}) in channel {channel}")

            if channel not in self.zombies:
                print(f"Channel {channel} not found in zombies dictionary")
                self.zombies[channel] = {}

            self.zombies[channel][zombie_id] = {"spawn_time": time.time(), "health": zombie_health, "name": zombie_name, "points": zombie_points}

            self.connection.privmsg(channel,
                                    f"A wild {zombie_name} (ID: {zombie_id}) appears! Type '.shoot {zombie_id}' to kill it!")

    def handle_shooting(self, c, e, parts):
        user = e.source.nick
        channel = e.target

        if self.bullets.get(user) == "exploded":
            c.privmsg(channel, f"Oh no, {user}! Your gun exploded! Type '.reload' to repair your gun.")
            return

        if len(parts) != 2:
            c.privmsg(channel, f"Invalid command format. Usage: .shoot <zombie_id>")
            return

        try:
            zombie_id = parts[1]
            if len(zombie_id) != 2 or not zombie_id.isdigit():
                raise ValueError

            if user not in self.bullets or self.bullets[user] <= 0:
                c.privmsg(channel, f"{user}, you are out of bullets. Type '.reload' to reload your gun.")
                return

            self.bullets[user] -= 1

            if random.random() < self.explosion_chance:
                self.bullets[user] = "exploded"
                c.privmsg(channel, f"Oh no, {user}! Your gun exploded!")
                self.scores[user] = max(self.scores.get(user, 0) - 10, 0)
                c.privmsg(channel,
                          f"{user}, due to the gun explosion you've lost 2 kills. Your current score is now {self.scores[user]}")
                self.save_scores()
            else:
                channel_lower = channel.lower()
                if zombie_id in self.zombies.get(channel_lower, {}):
                    zombie = self.zombies[channel_lower][zombie_id]
                    if "health" in zombie and zombie["health"] > 0:
                        zombie["health"] -= 1
                        if zombie["health"] == 0:
                            shot_time = time.time() - zombie["spawn_time"]
                            del self.zombies[channel_lower][zombie_id]
                            zombie_points = zombie["points"]
                            self.scores[user] = self.scores.get(user, 0) + zombie_points
                            c.privmsg(channel,
                                      f"Nice shot, {user}! You killed {zombie['name']} {zombie_id} in {shot_time:.2f} seconds and earned {zombie_points} points! Your current score is now {self.scores[user]}.")
                            self.save_scores()
                        else:
                            c.privmsg(channel, f"{user}, you hit {zombie['name']} {zombie_id}, but it's still alive with {zombie['health']} health.")
                    else:
                        c.privmsg(channel,
                                  f"Zombie {zombie_id} is not found. Keep an eye on the channel for more zombies!")
                else:
                    c.privmsg(channel, f"Zombie {zombie_id} is not found. Keep an eye on the channel for more zombies!")

        except ValueError:
            c.privmsg(channel, "Invalid command format. Usage: .shoot <zombie_id>")

    def handle_reloading(self, c, e):
        user = e.source.nick
        channel = e.target
        self.bullets[user] = 5
        if self.bullets.get(user) == "exploded":
            c.privmsg(channel, f"{user}, your gun has been fixed and reloaded!")
        else:
            c.privmsg(channel, f"{user}, your gun is reloaded!")

    def print_scores(self, c, e):
        channel = e.target
        if self.is_connected():
            c.privmsg(channel, "Check your score at https://www.twistednet.org/zombie/")

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

    def on_ctcp(self, c, e):
        super().on_ctcp(c, e)

        if e.arguments[0] == "VERSION":
            c.ctcp_reply(e.source.nick, "ZombieBot - By: gh0st")

    def run(self):
        self.load_zombies_state()
        super().start()

def main():
    server = "irc.twistednet.org"
    channel_list = ["#twisted2", "#dev"]
    nickname = "Zombie"

    bot = ZombieBot(channel_list, nickname, server)
    bot.start()

if __name__ == "__main__":
    main()
