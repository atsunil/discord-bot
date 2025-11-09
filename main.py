import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import re
import asyncio
import random

# Load environment variables from .env file 
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')  # Change this to use DISCORD_TOKEN

# If TOKEN is None, try getting it directly from environment
if not TOKEN:
    TOKEN = os.environ.get('DISCORD_TOKEN')

if not TOKEN:
    raise ValueError("No token found. Please set the DISCORD_TOKEN environment variable.")

# Constants
COMMAND_PREFIX = '?'
BANNED_WORDS = ['punda',]  # Add more banned words here
MAX_WARNINGS = 3
WARNING_EXPIRE_DAYS = 1
CUSTOM_EMOJIS = {
    "gay": "<:52469urgay:1437053191043813427>",
"22234boykisser": "<:22234boykisser:1437053188141486152>",
"6770la": "<:6770la:1437053185293287504>",
"2K8": "<:2K8:1437053115416313866>",
"WRIWD": "<:WRIWD:1437052654999310387>",
"Welcome": "<:Welcome:1437052650578509834>",
"thonk": "<:thonk:1437052647453622333>",
"Screenshot20230910121617": "<:Screenshot20230910121617:1437052639643963504>",
"scarytrollfacepngimage": "<:scarytrollfacepngimage:1437052636200304680>",
"Sad_Cat": "<:Sad_Cat_Thumbs_Up:1437052632400134164>",
"memed": "<:memed:1437052629036302527>",
"imoutdisappear": "<:imoutdisappear:1437052612791898234>",
"hellowell": "<:hellowell:1437052605829353583>",
"heHeh": "<:heHeh:1437052598850158792>",
"FunnyLookingCats": "<:FunnyLookingCats:1437052591099084903>",
"file": "<:file:1437052585994358901>",
"fatigued_mokou": "<:fatigued_mokou:1437052582953619499>",
"ef06b6c735a754e0ef35d6865c457015": "<:ef06b6c735a754e0ef35d6865c457015:1437052580160344224>",
"DankMemesTriggerd": "<:DankMemesTriggerd:1437052577001897984>",
"Chopper_CoolGlasses": "<:Chopper_CoolGlasses:1437052571243253851>",
"cat_stab": "<:cat_stab:1437052566604353547>",
"cat": "<:cat:1437052560434266265>",
"buckshot": "<:buckshot:1437052555380392048>",
"bc85e388fb78282389bc6a0a0e07c3f0": "<:bc85e388fb78282389bc6a0a0e07c3f0:1437052525055447051>",
"767904catass": "<:767904catass:1437052521389490331>",
"666226cat": "<:666226cat:1437052510685757450>",
"661600sillycat": "<:661600sillycat:1437052507506475018>",
"621730meowl": "<:621730meowl:1437052503861624935>",
"483862laughingcat": "<:483862laughingcat:1437052497821696050>",
"417506cutecat": "<:417506cutecat:1437052489064124486>",
"353281cat": "<:353281cat:1437052482856685610>",
"154597catstare2": "<:154597catstare2:1437052471980593172>",
"65588catlewfuc": "<:65588catlewfuc:1437052466993696779>",
"65469basilleafcat": "<:65469basilleafcat:1437052462178631741>",
"37705doraemonshock": "<:37705doraemonshock:1437052459250876579>",
"14597catheh": "<:14597catheh:1437052456302411816>",
"10893cryingcat": "<:10893cryingcat:1437052453379113051>",
"9889pain": "<:9889pain:1437052438782808114>",
"9870kannaohwelcome": "<:9870kannaohwelcome:1437052432906719292>",
"9334_b_ryukosquish": "<:9334_b_ryukosquish:1437052423897354412>",
"9028uwu": "<:9028uwu:1437052419392405565>",
"8916pepeshoot1": "<:8916pepeshoot1:1437052417106776188>",
"8859pepemoney": "<:8859pepemoney:1437052412937637912>",
"8810catwashingclothes": "<:8810catwashingclothes:1437052405681360997>",
"8730kissyou": "<:8730kissyou:1437052397443612812>",
"8651kannaeating": "<:8651kannaeating:1437052390133203024>",
"8379_cough_cat": "<:8379_cough_cat:1437052382080139394>",
"7775_akukuha": "<:7775_akukuha:1437052360672284672>",
"7381pepefinger": "<:7381pepefinger:1437052353659277424>",
"6876_Rainbow_Blob_Trash": "<:6876_Rainbow_Blob_Trash:1437052343601594408>",
"6834pepesimp": "<:6834pepesimp:1437052340069732373>",
"6135betsmirk": "<:6135betsmirk:1437052336844312658>",
"6004spongekong": "<:6004spongekong:1437052327499399359>",
"5669chipichapa": "<:5669chipichapa:1437052323699495024>",
"5528_ontherun": "<:5528_ontherun:1437052293089595492>",
"5498_catJAM": "<:5498_catJAM:1437052286483304632>",
"4852catshake": "<:4852catshake:1437052277591642133>",
"4838_despair": "<:4838_despair:1437052265503395920>",
"4710_b_shinobusquishy": "<:4710_b_shinobusquishy:1437052259778428988>",
"4365actuallyim": "<:4365actuallyim:1437052239897296997>",
"4297pepehacker": "<:4297pepehacker:1437052230783074425>",
"4221dwayneeyebrow": "<:4221dwayneeyebrow:1437052227985346703>",
"3568catkiss": "<:3568catkiss:1437052223963271299>",
"3424_disgustanjirou1": "<:3424_disgustanjirou1:1437052217608769536>",
"3416rickroll": "<:3416rickroll:1437052214337077381>",
"3401_stop_pls": "<:3401_stop_pls:1437052205583564950>",
"3124_cry": "<:3124_cry:1437052152412639382>",
"2813waitwaitwait": "<:2813waitwaitwait:1437052140072734861>",
"2579catyipee": "<:2579catyipee:1437052129960398889>",
"2112_HD_wheeze_emoji": "<:2112_HD_wheeze_emoji:1437052104849096704>",
"2019_jeanluc_melenchon": "<:2019_jeanluc_melenchon:1437052101460230184>",
"2012_RISITAS": "<:2012_RISITAS:1437052097970573424>",
"1786shockedcat": "<:1786shockedcat:1437052093709025310>",
"1782galaxybrainmeme": "<:1782galaxybrainmeme:1437052081868640378>",
"1720kannauhh": "<:1720kannauhh:1437052073366523925>",
"1525christmasmilitary1pfpsgg": "<:1525christmasmilitary1pfpsgg:1437052069646176287>",
"1383ameliawatsonreading": "<:1383ameliawatsonreading:1437052021843693640>",
"1383ameliawatsonfast": "<:1383ameliawatsonfast:1437052018530189382>",
"1146_dance": "<:1146_dance:1437051972690772008>"
}

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warnings = {}  # {user_id: [(timestamp, reason), ...]}

    def _get_active_warnings(self, user_id):
        """Get warnings that haven't expired"""
        if user_id not in self.warnings:
            return []
        
        cutoff = datetime.now() - timedelta(days=WARNING_EXPIRE_DAYS)
        active_warnings = [w for w in self.warnings[user_id] if w[0] > cutoff]
        self.warnings[user_id] = active_warnings
        return active_warnings

    def has_role(self, member, allowed_roles):
        """Check if member has any of the allowed roles"""
        return any(role.name in allowed_roles for role in member.roles)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if message is just the prefix
        if message.content == COMMAND_PREFIX:
            await message.channel.send("Hi! 👋 Type `?help` to see my commands!")
            return

        # Randomly decide whether to send a sticker (e.g., 40% chance)
        if random.random() < 0.40:  # Changed from 0.30 to 0.40 for 40% chance
            try:
                sticker_id = random.choice(CUSTOM_EMOJIS)
                # Get the sticker object
                sticker = await message.guild.fetch_sticker(int(sticker_id))
                # Send a message with the sticker
                await message.channel.send(stickers=[sticker])
            except discord.Forbidden:
                logging.warning(f"Cannot send stickers in channel: {message.channel.id}")
            except Exception as e:
                logging.error(f"Error sending sticker: {e}")

        # Check for banned words
        content_lower = message.content.lower()
        if any(word in content_lower for word in BANNED_WORDS):
            await message.delete()
            await self._handle_violation(message)

    async def _handle_violation(self, message):
        user_id = message.author.id
        
        # Add warning
        if user_id not in self.warnings:
            self.warnings[user_id] = []
        
        self.warnings[user_id].append((datetime.now(), "Inappropriate language"))
        active_warnings = self._get_active_warnings(user_id)
        warning_count = len(active_warnings)

        if warning_count == 1:
            await message.author.send(
                f"⚠️ Warning: Inappropriate language is not allowed in {message.guild.name}. "
                "This is your first warning."
            )
        elif warning_count == 2:
            await message.author.send(
                f"⚠️ Final Warning: Continued use of inappropriate language in {message.guild.name} "
                "will result in being kicked."
            )
        else:
            await message.author.send(
                f"You have been kicked from {message.guild.name} for repeated violations."
            )
            await message.channel.send(
                f"{message.author.mention} has been kicked for repeated violations."
            )
            await message.guild.kick(message.author, reason="Repeated violations")

    @commands.command(name="warnings")
    async def check_warnings(self, ctx, member: discord.Member):
        """Check warnings for a user"""
        warnings = self._get_active_warnings(member.id)
        if not warnings:
            await ctx.send(f"{member.display_name} has no active warnings.")
            return

        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            color=discord.Color.yellow()
        )
        for timestamp, reason in warnings:
            embed.add_field(
                name=f"Warning on {timestamp.strftime('%Y-%m-%d %H:%M')}",
                value=reason,
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name="del")
    async def delete_messages(self, ctx, amount: int):
        """Delete multiple messages at once"""
        if amount <= 0:
            await ctx.send("Please specify a positive number of messages to delete.")
            return
            
        if amount > 100:
            await ctx.send("You can only delete up to 100 messages at once.")
            return

        # Send confirmation message
        confirm_msg = await ctx.send(f"Are you sure you want to delete {amount} messages? React with ✅ to confirm.")
        await confirm_msg.add_reaction("✅")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "✅" and reaction.message == confirm_msg

        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            # Delete the confirmation message
            await confirm_msg.delete()
            
            # Delete the specified number of messages
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
            
            # Send confirmation and log the action
            success_msg = await ctx.send(f"🗑️ Successfully deleted {len(deleted)-1} messages.")
            logging.info(f"Del command used by {ctx.author} in {ctx.channel}: {len(deleted)-1} messages deleted")
            
            # Delete the success message after 5 seconds
            await success_msg.delete(delay=5)
            
        except TimeoutError:
            await confirm_msg.delete()
            await ctx.send("Delete command cancelled due to timeout.", delete_after=5)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete messages in this channel!")
            
        except Exception as e:
            logging.error(f"Error in del command: {e}")
            await ctx.send("An error occurred while trying to delete messages.")

    @commands.command(name="nuke")
    async def nuke_message(self, ctx, member: discord.Member, count: int, *, message: str):
        """Send repeated messages to a user"""
        if count <= 0:
            await ctx.send("Please specify a positive number of messages.")
            return
            
        if count > 50:
            await ctx.send("You can only send up to 50 messages at once.")
            return

        # Send confirmation message
        confirm_msg = await ctx.send(f"Are you sure you want to send {count} messages to {member.mention}? React with ✅ to confirm.")
        await confirm_msg.add_reaction("✅")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "✅" and reaction.message == confirm_msg

        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            await confirm_msg.delete()

            # Send messages with a small delay between each
            for i in range(count):
                await member.send(f"{message}")
                await asyncio.sleep(1)  # 1 second delay between messages
            
            success_msg = await ctx.send(f"✅ Successfully sent {count} messages to {member.mention}")
            logging.info(f"Nuke command used by {ctx.author} on {member}: {count} messages sent")
            
            await success_msg.delete(delay=5)
            
        except asyncio.TimeoutError:
            await confirm_msg.delete()
            await ctx.send("Nuke command cancelled due to timeout.", delete_after=5)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to send messages to this user!")
            
        except Exception as e:
            logging.error(f"Error in nuke command: {e}")
            await ctx.send("An error occurred while trying to send messages.")

    @commands.command(name="mute")
    async def mute_user(self, ctx, member: discord.Member, *, reason: str = None):
        """Temporarily mute a user"""
        try:
            # Default mute duration: 1 hour
            duration = timedelta(hours=1)
            await member.timeout(duration, reason=reason)
            
            # Create embed for mute notification
            embed = discord.Embed(
                title="User Muted",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Duration", value="1 hour", inline=True)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)

            await ctx.send(embed=embed)
            logging.info(f"User {member} muted by {ctx.author} for reason: {reason}")

        except discord.Forbidden:
            await ctx.send("I don't have permission to mute this user!")
        except Exception as e:
            logging.error(f"Error in mute command: {e}")
            await ctx.send("An error occurred while trying to mute the user.")

    @commands.command(name="unmute")
    async def unmute_user(self, ctx, member: discord.Member):
        """Remove timeout/mute from a user"""
        try:
            await member.timeout(None)  # Remove timeout
            
            # Create embed for unmute notification
            embed = discord.Embed(
                title="User Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            logging.info(f"User {member} unmuted by {ctx.author}")

        except discord.Forbidden:
            await ctx.send("I don't have permission to unmute this user!")
        except Exception as e:
            logging.error(f"Error in unmute command: {e}")
            await ctx.send("An error occurred while trying to unmute the user.")

    @commands.command(name="sticker")
    async def convert_to_sticker(self, ctx, emoji_name: str):
        """Convert emoji name to sticker. Usage: ?sticker [emoji_name]
        Example: ?sticker cat"""
        try:
            # Remove any colons from the input if present
            emoji_name = emoji_name.strip(':')
            
            # Check if emoji exists in CUSTOM_EMOJIS
            if emoji_name in CUSTOM_EMOJIS:
                sticker_id = CUSTOM_EMOJIS[emoji_name]
                await ctx.message.delete()  # Delete the command message
                await ctx.send(sticker_id)
            else:
                # Create a list of similar emoji names for suggestions
                similar_emojis = [name for name in CUSTOM_EMOJIS.keys() 
                                if emoji_name.lower() in name.lower()]
                
                if similar_emojis:
                    suggestions = '\n'.join(similar_emojis[:5])  # Show up to 5 suggestions
                    await ctx.send(f"❌ Emoji '{emoji_name}' not found. Did you mean:\n{suggestions}")
                else:
                    await ctx.send(f"❌ Emoji '{emoji_name}' not found. Use one of the available emoji names.")
            
        except Exception as e:
            logging.error(f"Error in sticker command: {e}")
            await ctx.send("An error occurred while converting to sticker.")

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = {}  # {user_id: [(timestamp, message, channel_id), ...]}
        self.reminder_task = self.bot.loop.create_task(self.check_reminders())

    def parse_time(self, time_str):
        """Convert time string to timedelta (e.g., '1h30m', '2d', '5m')"""
        time_units = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days',
            'w': 'weeks'
        }
        
        total_seconds = 0
        pattern = re.compile(r'(\d+)([smhdw])')
        matches = pattern.findall(time_str.lower())
        
        if not matches:
            raise ValueError("Invalid time format")
            
        for value, unit in matches:
            unit_name = time_units.get(unit)
            if unit_name:
                kwargs = {unit_name: int(value)}
                total_seconds += timedelta(**kwargs).total_seconds()
                
        return timedelta(seconds=total_seconds)

    @commands.command(name="remindme")
    async def set_reminder(self, ctx, time_str: str, *, message: str):
        """Set a reminder. Usage: ?remindme [time] [message]
        Example: ?remindme 1h30m Take a break
        Time units: s (seconds), m (minutes), h (hours), d (days), w (weeks)"""
        try:
            delay = self.parse_time(time_str)
            if delay.total_seconds() < 10:
                await ctx.send("Reminder time must be at least 10 seconds!")
                return
                
            if delay.total_seconds() > 30 * 24 * 60 * 60:  # 30 days
                await ctx.send("Reminder time cannot exceed 30 days!")
                return

            reminder_time = datetime.now() + delay
            user_id = ctx.author.id
            
            if user_id not in self.reminders:
                self.reminders[user_id] = []
                
            self.reminders[user_id].append((reminder_time, message, ctx.channel.id))
            
            # Format time string for confirmation message
            time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
            await ctx.send(f"✅ I'll remind you about: '{message}' on {time_str}")
            
        except ValueError as e:
            await ctx.send("❌ Invalid time format! Use format like: 1h30m, 2d, 5m")
        except Exception as e:
            logging.error(f"Error setting reminder: {e}")
            await ctx.send("An error occurred while setting the reminder.")

    @commands.command(name="remindto")
    async def remind_to(self, ctx, member: discord.Member, time_str: str, *, message: str):
        """Set a reminder for another user. Usage: ?remindto @user [time] [message]
        Example: ?remindto @username 1h30m Time for meeting!
        Time units: s (seconds), m (minutes), h (hours), d (days), w (weeks)"""
        try:
            delay = self.parse_time(time_str)
            if delay.total_seconds() < 10:
                await ctx.send("Reminder time must be at least 10 seconds!")
                return
                
            if delay.total_seconds() > 30 * 24 * 60 * 60:  # 30 days
                await ctx.send("Reminder time cannot exceed 30 days!")
                return

            reminder_time = datetime.now() + delay
            target_id = member.id
            
            # Store who set the reminder
            reminder_data = (reminder_time, message, ctx.channel.id, ctx.author.id)
            
            if target_id not in self.reminders:
                self.reminders[target_id] = []
                
            self.reminders[target_id].append(reminder_data)
            
            # Format time string for confirmation message
            time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
            await ctx.send(f"✅ I'll remind {member.mention} about: '{message}' on {time_str}")
            
            # Notify the target user
            try:
                await member.send(f"📝 {ctx.author.name} set a reminder for you: '{message}' on {time_str}")
            except discord.Forbidden:
                await ctx.send(f"⚠️ Note: Couldn't send DM to {member.mention}. They will only see the reminder in the server.")
            
        except ValueError as e:
            await ctx.send("❌ Invalid time format! Use format like: 1h30m, 2d, 5m")
        except Exception as e:
            logging.error(f"Error setting reminder: {e}")
            await ctx.send("An error occurred while setting the reminder.")

    async def check_reminders(self):
        """Background task to check and send reminders"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                now = datetime.now()
                for user_id, reminders in list(self.reminders.items()):
                    remaining_reminders = []
                    for reminder_data in reminders:
                        reminder_time = reminder_data[0]
                        message = reminder_data[1]
                        channel_id = reminder_data[2]
                        setter_id = reminder_data[3] if len(reminder_data) > 3 else None

                        if now >= reminder_time:
                            try:
                                # Get the target user and channel
                                user = await self.bot.fetch_user(user_id)
                                channel = self.bot.get_channel(channel_id)
                                
                                # Get the reminder setter if available
                                setter = None
                                if setter_id:
                                    setter = await self.bot.fetch_user(setter_id)
                                
                                # Send DM to the target user
                                dm_message = f"⏰ Reminder: {message}"
                                if setter:
                                    dm_message = f"⏰ Reminder from {setter.name}: {message}"
                                await user.send(dm_message)

                                # Send message in the channel
                                if channel:
                                    channel_message = f"✅ Reminder for {user.mention}: {message}"
                                    if setter:
                                        channel_message = f"✅ Reminder from {setter.mention} to {user.mention}: {message}"
                                    await channel.send(channel_message)
                                    
                            except discord.Forbidden:
                                if channel:
                                    await channel.send(f"❌ Couldn't send reminder DM to {user.mention}. Reminder: {message}")
                            except Exception as e:
                                logging.error(f"Error sending reminder: {e}")
                        else:
                            remaining_reminders.append(reminder_data)
                    
                    if remaining_reminders:
                        self.reminders[user_id] = remaining_reminders
                    else:
                        del self.reminders[user_id]
                        
            except Exception as e:
                logging.error(f"Error in reminder check: {e}")
                
            await asyncio.sleep(10)  # Check every 10 seconds

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.reminder_task.cancel()

class Bot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(Moderation(self))
        await self.add_cog(ReminderCog(self))

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.change_presence(activity=discord.Game(name=f"{COMMAND_PREFIX}help"))

def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = Bot(command_prefix=COMMAND_PREFIX, intents=intents)
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Error running bot: {e}")

if __name__ == "__main__":
    main()
