import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import json
import os
from datetime import datetime, timedelta
import io
import time
import platform
import psutil
import random
from typing import Optional

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

# Admin check decorator
def is_admin():
    async def predicate(ctx):
        if not isinstance(ctx.channel, discord.TextChannel):
            return False
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# Store active DM channels and their configurations
active_dms = {}  # {author_id: {'user': target_user, 'channel': channel, 'message_map': {}}}

# Ensure directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('files', exist_ok=True)

# Default configuration
DEFAULT_CONFIG = {
    'prefix': '!',
    'default_logging': True,
    'max_file_size': 8388608,  # 8MB
    'allowed_file_types': ['.txt', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.pdf', '.zip', '.docx', '.xlsx']  # Extended file types
}

# Helper functions
def format_duration(seconds):
    """Format seconds into human readable time"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    parts = []
    if days > 0:
        parts.append(f"{int(days)}d")
    if hours > 0:
        parts.append(f"{int(hours)}h")
    if minutes > 0:
        parts.append(f"{int(minutes)}m")
    if seconds > 0 or not parts:
        parts.append(f"{int(seconds)}s")
    
    return " ".join(parts)

def get_system_info():
    """Get system information"""
    return {
        'os': platform.system(),
        'python_version': platform.python_version(),
        'discord_version': discord.__version__,
        'cpu_usage': psutil.cpu_percent(),
        'memory_usage': psutil.virtual_memory().percent,
        'uptime': time.time() - psutil.boot_time()
    }

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            loaded_config = json.load(f)
            # Update with any missing default values
            for key, value in DEFAULT_CONFIG.items():
                if key not in loaded_config:
                    loaded_config[key] = value
    except FileNotFoundError:
        loaded_config = DEFAULT_CONFIG.copy()
        # Save the default config
        with open('config.json', 'w') as f:
            json.dump(loaded_config, f, indent=4)
    return loaded_config

# Save configuration
def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

config = load_config()

# Update bot's command prefix
def update_command_prefix():
    bot.command_prefix = config['prefix']

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user.name} (ID: {bot.user.id})')
    print(f'Connected to {len(bot.guilds)} servers.')
    server_names = [guild.name for guild in bot.guilds]
    print(f'Currently serving the following servers: {", ".join(server_names)}')
    await bot.change_presence(activity=discord.Game(name=f"{config['prefix']}help for list of commands"))
    print('Ready to assist administrators! 🎉')

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    if message.author == bot.user:
        return

    # For DM responses from target user
    if isinstance(message.channel, discord.DMChannel):
        await handle_dm_response(message)
    
    # For messages from admin initiator
    elif message.author.id in active_dms and not message.content.startswith(config['prefix']):
        # Check if the author is still an admin
        guild = bot.get_guild(message.guild.id)
        member = await guild.fetch_member(message.author.id)
        if member and member.guild_permissions.administrator:
            await handle_initiator_message(message)
        else:
            # Remove the session if the user is no longer an admin
            await stop_dm(message.author.id)
            await message.channel.send("Your DM session has been terminated as you are no longer an administrator.")
    
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction adding"""
    if user == bot.user:
        return
        
    # Check if reaction is from the initiator
    if user.id in active_dms:
        dm_info = active_dms[user.id]
        # Get the corresponding message in the DM
        if reaction.message.id in dm_info.get('message_map', {}):
            target_message_id = dm_info['message_map'][reaction.message.id]
            try:
                # Get the message from DM channel
                channel = await dm_info['user'].create_dm()
                message = await channel.fetch_message(target_message_id)
                # Add the same reaction
                await message.add_reaction(reaction.emoji)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                print(f"Error mirroring reaction: {e}")

@bot.event
async def on_reaction_remove(reaction, user):
    """Handle reaction removal"""
    if user == bot.user:
        return
        
    # Check if reaction is from the initiator
    if user.id in active_dms:
        dm_info = active_dms[user.id]
        # Get the corresponding message in the DM
        if reaction.message.id in dm_info.get('message_map', {}):
            target_message_id = dm_info['message_map'][reaction.message.id]
            try:
                # Get the message from DM channel
                channel = await dm_info['user'].create_dm()
                message = await channel.fetch_message(target_message_id)
                # Remove the same reaction
                await message.remove_reaction(reaction.emoji, bot.user)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                print(f"Error removing reaction: {e}")

async def handle_dm_response(message):
    """Handle incoming DMs from target users"""
    for author_id, dm_info in active_dms.items():
        if dm_info['user'].id == message.author.id:
            channel = dm_info['channel']
            
            embed = discord.Embed(
                description=message.content if message.content else "Sent an attachment",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.set_author(name=f"Message from {message.author.name}", 
                           icon_url=message.author.avatar.url if message.author.avatar else None)

            # Handle attachments
            files_to_send = []
            if message.attachments:
                for attachment in message.attachments:
                    file_ext = os.path.splitext(attachment.filename)[1].lower()
                    if file_ext in config['allowed_file_types']:
                        if attachment.size <= config['max_file_size']:
                            # Download the file content
                            file_data = await attachment.read()
                            # Create a discord.File object with BytesIO
                            file = discord.File(fp=io.BytesIO(file_data), filename=attachment.filename)
                            files_to_send.append(file)
                            embed.add_field(name="Attachment", value=attachment.filename)
                        else:
                            embed.add_field(name="Error", value=f"File too large: {attachment.filename}")
                    else:
                        embed.add_field(name="Error", value=f"File type not allowed: {attachment.filename}")

            # Send message with any attachments
            sent_message = await channel.send(embed=embed, files=files_to_send)
            
            # Store message mapping
            if 'message_map' not in dm_info:
                dm_info['message_map'] = {}
            dm_info['message_map'][sent_message.id] = message.id

async def handle_initiator_message(message):
    """Handle outgoing messages from initiator"""
    dm_info = active_dms[message.author.id]
    target_user = dm_info['user']
    try:
        files_to_send = []
        
        # Handle attachments
        if message.attachments:
            for attachment in message.attachments:
                file_ext = os.path.splitext(attachment.filename)[1].lower()
                if file_ext in config['allowed_file_types']:
                    if attachment.size <= config['max_file_size']:
                        # Download the file content
                        file_data = await attachment.read()
                        # Create a discord.File object with BytesIO
                        file = discord.File(fp=io.BytesIO(file_data), filename=attachment.filename)
                        files_to_send.append(file)
                    else:
                        await message.channel.send(f"File too large to send: {attachment.filename}")
                else:
                    await message.channel.send(f"File type not allowed: {attachment.filename}")
        
        # Send message with any attachments
        if message.content or files_to_send:
            sent_message = await target_user.send(
                content=message.content if message.content else None,
                files=files_to_send
            )
            
            # Store message mapping for reactions
            if sent_message:
                if 'message_map' not in dm_info:
                    dm_info['message_map'] = {}
                dm_info['message_map'][message.id] = sent_message.id
                
    except discord.Forbidden:
        await message.channel.send("Unable to send message. The user might have blocked the bot.")
        await stop_dm(message.author.id)
    except Exception as e:
        await message.channel.send(f"Error sending message: {str(e)}")

# Modify all commands to require admin permissions
@bot.command()
@is_admin()
async def status(ctx):
    """Show bot and system status"""
    sys_info = get_system_info()
    
    embed = discord.Embed(
        title="Bot Status",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # Bot info
    embed.add_field(
        name="Bot Information",
        value=f"""
        **Status:** 🟢 Online
        **Latency:** {round(bot.latency * 1000)}ms
        **Active DM Sessions:** {len(active_dms)}
        **Command Prefix:** {config['prefix']}
        """,
        inline=False
    )
    
    # System info
    embed.add_field(
        name="System Information",
        value=f"""
        **OS:** {sys_info['os']}
        **Python:** {sys_info['python_version']}
        **Discord.py:** {sys_info['discord_version']}
        **CPU Usage:** {sys_info['cpu_usage']}%
        **Memory Usage:** {sys_info['memory_usage']}%
        **System Uptime:** {format_duration(sys_info['uptime'])}
        """,
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
@is_admin()
async def ping(ctx):
    """Check bot's latency"""
    start_time = time.time()
    message = await ctx.send("Pinging...")
    end_time = time.time()
    
    api_latency = round(bot.latency * 1000)
    bot_latency = round((end_time - start_time) * 1000)
    
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    embed.add_field(name="Bot Latency", value=f"{bot_latency}ms")
    embed.add_field(name="API Latency", value=f"{api_latency}ms")
    
    await message.edit(content=None, embed=embed)

@bot.command()
@is_admin()
async def userinfo(ctx, user_id: Optional[int] = None):
    """Get information about a user"""
    try:
        user = await bot.fetch_user(user_id) if user_id else ctx.author
        
        embed = discord.Embed(
            title="User Information",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        embed.add_field(name="Username", value=user.name)
        embed.add_field(name="User ID", value=user.id)
        embed.add_field(name="Bot", value="Yes" if user.bot else "No")
        embed.add_field(name="Account Created", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"))
        
        if isinstance(ctx.channel, discord.TextChannel):
            member = ctx.guild.get_member(user.id)
            if member:
                embed.add_field(
                    name="Server Join Date", 
                    value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    inline=False
                )
                embed.add_field(
                    name="Roles",
                    value=" ".join([role.mention for role in member.roles[1:]]) or "No roles",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    except discord.NotFound:
        await ctx.send("User not found.")
    except Exception as e:
        await ctx.send(f"Error retrieving user information: {str(e)}")

@bot.command()
@is_admin()
async def clear(ctx, amount: int = 10):
    """Clear specified number of messages"""
    if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command can only be used in server channels.")
        return
        
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("You don't have permission to use this command.")
        return
        
    if amount < 1 or amount > 100:
        await ctx.send("Please specify a number between 1 and 100.")
        return
        
    deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include command message
    msg = await ctx.send(f"Deleted {len(deleted)-1} messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command()
@is_admin()
async def backup(ctx):
    """Create a backup of config and logs"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need administrator permissions to use this command.")
        return
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f'backup_{timestamp}'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup config
    try:
        with open('config.json', 'r') as src, open(f'{backup_dir}/config.json', 'w') as dst:
            json.dump(json.load(src), dst, indent=4)
    except Exception as e:
        await ctx.send(f"Error backing up config: {str(e)}")
        return
    
    # Backup logs
    try:
        for file in os.listdir('logs'):
            if file.endswith('.json'):
                os.system(f'cp logs/{file} {backup_dir}/{file}')
    except Exception as e:
        await ctx.send(f"Error backing up logs: {str(e)}")
        return
    
    # Create zip file
    try:
        import shutil
        zip_name = f'{backup_dir}.zip'
        shutil.make_archive(backup_dir, 'zip', backup_dir)

        # Send zip file
        await ctx.send(
            "Here's your backup:",
            file=discord.File(f'{zip_name}')
        )
        
        # Cleanup
        shutil.rmtree(backup_dir)
        os.remove(zip_name)
    except Exception as e:
        await ctx.send(f"Error creating backup zip: {str(e)}")

@bot.command()
@is_admin()
async def prefix(ctx, new_prefix: str):
    """Change the bot's command prefix"""
    if len(new_prefix) > 3:
        await ctx.send("Prefix must be 3 characters or less.")
        return
        
    config['prefix'] = new_prefix
    save_config()
    update_command_prefix()
    
    embed = discord.Embed(
        title="Prefix Updated",
        description=f"Command prefix has been changed to: {new_prefix}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    
    # Update bot's status
    await bot.change_presence(activity=discord.Game(name=f"{new_prefix}panel for help"))

@bot.command()
@is_admin()
async def startmsg(ctx, user_id: int):
    """Start a DM session"""
    try:
        if ctx.author.id in active_dms:
            await ctx.send("You already have an active DM session. Use !stopmsg first.")
            return

        target_user = await bot.fetch_user(user_id)
        
        active_dms[ctx.author.id] = {
            'user': target_user,
            'channel': ctx.channel,
            'message_map': {}
        }
        
        embed = discord.Embed(
            title="DM Session Started",
            description=f"Now messaging {target_user.name}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
    except discord.NotFound:
        await ctx.send("User not found. Please check the ID.")
    except discord.HTTPException as e:
        await ctx.send(f"Discord API error: {str(e)}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")

@bot.command()
@is_admin()
async def stopmsg(ctx):
    """Stop active DM session"""
    if ctx.author.id in active_dms:
        target_user = active_dms[ctx.author.id]['user']
        await stop_dm(ctx.author.id)
        
        embed = discord.Embed(
            title="DM Session Ended",
            description=f"Stopped messaging {target_user.name}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("No active DM session found.")

@bot.command()
@is_admin()
async def export(ctx):
    """Export chat logs"""
    if ctx.author.id in active_dms:
        filename = f'logs/dm_{ctx.author.id}_{datetime.now().strftime("%Y%m%d")}.json'
        try:
            await ctx.send("Here are your chat logs:", file=discord.File(filename))
        except FileNotFoundError:
            await ctx.send("No logs found.")
    else:
        await ctx.send("No active DM session found.")

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Make buttons persistent
        
        # Add Server Invite button
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Invite the Bot",
            url="https://discord.gg/your-invite-link",  # Replace with your server invite
            emoji="🔧"
        ))
        
        # Add GitHub button
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="GitHub",
            url="https://github.com/zejestry",  # Replace with your GitHub repo
            emoji="📦"
        ))
        
        # Add Donate button
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Support Development",
            url="https://www.paypal.com/paypalme/zejestry",  # Replace with your donation link
            emoji="💖"
        ))

@bot.command()
@is_admin()
async def helpme(ctx, command: str = None):
    """Enhanced help command"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("This bot is only available to administrators.")
        return
        
    cmd = bot.get_command(command)
    if cmd is None:
        await ctx.send(f"Command `{command}` not found.")
        return
        
    embed = discord.Embed(
        title=f"Help: {cmd.name}",
        description=cmd.helpme or "No description available.",
        color=discord.Color.blue()
    )
    
    usage = f"{config['prefix']}{cmd.name}"
    if cmd.signature:
        usage += f" {cmd.signature}"
    embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
    
    if cmd.aliases:
        embed.add_field(name="Aliases", value=", ".join(cmd.aliases), inline=False)
    
    # Add buttons to help command as well
    view = PanelView()
    await ctx.send(embed=embed, view=view)

@bot.command()
async def panel(ctx):
    """Display the command panel"""
    ascii_art = """
        ██████╗  █████╗ ███╗   ██╗███████╗██╗     
        ██╔══██╗██╔══██╗████╗  ██║██╔════╝██║     
        ██████╔╝███████║██╔██╗ ██║█████╗  ██║     
        ██╔═══╝ ██╔══██║██║╚██╗██║██╔══╝  ██║     
        ██║     ██║  ██║██║ ╚████║███████╗███████╗
        ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
@ᶻᵉʲᵉˢᵗʳʸ
    """
    
    embed = discord.Embed(
        title="Administrator Command Panel",
        description=f"```\n{ascii_art}```\n**List of available administrator commands:**",
        color=discord.Color.blue()
    )
    
    # Basic Commands section
    embed.add_field(
        name="вαѕι¢ ¢σммαη∂ѕ",
        value=f"""
        `{config['prefix']}helpme [command]` - Show help for all or specific command
        `{config['prefix']}panel` - Show this command panel
        `{config['prefix']}startmsg <user_id>` - Start a DM session
        `{config['prefix']}stopmsg` - Stop active DM session
        `{config['prefix']}export` - Export chat logs
        `{config['prefix']}prefix <new_prefix>` - Change command prefix
        """,
        inline=False
    )
    
    # Utility Commands section
    embed.add_field(
        name="υтιℓιту ¢σммαη∂ѕ",
        value=f"""
        `{config['prefix']}status` - Show bot and system status
        `{config['prefix']}ping` - Check bot latency
        `{config['prefix']}userinfo [user_id]` - Get user information
        `{config['prefix']}clear <amount>` - Clear messages (default: 10)
        `{config['prefix']}backup` - Create config and logs backup
        """,
        inline=False
    )
    
    # How to Use section
    embed.add_field(
        name="нσω тσ υѕє",
        value=f"""
        1. Start a DM session with `{config['prefix']}startmsg <user_id>`
           - ᴛʏᴘᴇ ᴀɴʏ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ꜱᴇɴᴅ ɪᴛ ᴛᴏ ᴛʜᴇ ᴜꜱᴇʀ
           - ᴛʜᴇɪʀ ʀᴇᴘʟɪᴇꜱ ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ɪɴ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ
           - ᴜꜱᴇ `{config['prefix']}ꜱᴛᴏᴘᴍꜱɢ` ᴛᴏ ᴇɴᴅ ᴛʜᴇ ꜱᴇꜱꜱɪᴏɴ
        """,
        inline=False
    )

    # Support Links section
    embed.add_field(
        name="ѕυρρσят & ℓιηкѕ",
        value="Click the buttons below to join our community, view source code, or support development! 🚀",
        inline=False
    )
    
    # Create view with buttons and send
    view = PanelView()
    await ctx.send(embed=embed, view=view)

async def stop_dm(author_id):
    """Helper function to stop DM session and clean up"""
    if author_id in active_dms:
        del active_dms[author_id]
        
        # Error handling for non-admin users
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("This bot is only available to administrators.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore command not found errors
    else:
        print(f'Error: {str(error)}')

# Run the bot (replace YOUR_BOT_TOKEN with your bot token)
if __name__ == "__main__":
    bot.run("YOUR_BOT_TOKEN")