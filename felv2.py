import logging, os
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import logging
import discord
from discord.ext import commands
from discord.ui import Button, Modal, View, InputText, Select
#from discord.commands import Option
from discord import Embed, Member, Option

from dotenv import load_dotenv

class PersistentViewBot(commands.Bot):
    def __init__(self):
        load_dotenv('.env')
        intents = discord.Intents.all()
        super().__init__(command_prefix = '%%', intents=intents)
        self.persistent_views_added = False

    async def on_ready(self):
        global user_message_associations
        try:
            with open('user_message_associations.json', 'r') as f:
                # Convert lists back to tuples after JSON deserialization
                user_message_associations = [tuple(pair) for pair in json.load(f)]
        except FileNotFoundError:
            user_message_associations = []

        if not self.persistent_views_added:
            self.add_view(InitialChoicesView())
            self.add_view(UnlockView())

            self.persistent_views_added = True
            print(f'Logged in as {bot.user} with an ID of {bot.user.id}')
            
bot = PersistentViewBot()
bot.remove_command('help')

# Intents
#intents = discord.Intents.all()
#bot = commands.Bot(intents=intents)



LOGS_CHANNEL_ID = int(os.getenv("LOGS_CHANNEL_ID"))
LEADERSHIP_ROLE_ID = int(os.getenv("LEADERSHIP_ROLE_ID"))
BARRICADE_CHANNEL_ID = int(os.getenv("BARRICADE_CHANNEL_ID"))
ALLIANCE_ID = 1157027714893631599

def save_associations():
    with open('user_message_associations.json', 'w') as f:
        # Convert tuples in the list to lists for JSON serialization
        json.dump([list(pair) for pair in user_message_associations], f)

class InitialChoicesView(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, timeout=None)
        self.add_item(InitialChoicesSelect())

class UnlockView(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, timeout=None)
        self.add_item(UnlockButton())

class RegisterSelectView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, timeout=None)
        self.add_item(RegisterSelect())

class SpeedupTypeView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_item(SpeedupTypeSelect())

class RegisterSelect(Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, placeholder="Choose an option...", min_values=1, max_values=1)
        self.add_option(label="Troops", description="Register your troops speedups")
        self.add_option(label="Research", description="Register your research speedups")
        self.add_option(label="Construction", description="Register your construction speedups")
    
    async def callback(self, interaction: discord.Interaction):
        # Determine the speedup type based on the selected option
        speedup_type = self.values[0].lower()
        
        # Open a modal when an option is selected, passing the speedup type
        modal = DaysModal(speedup_type=speedup_type, title=f"Register {self.values[0]} Speedups")
        await interaction.response.send_modal(modal)

class SpeedupTypeSelect(Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, placeholder="Choose an option...", min_values=1, max_values=1)
        self.add_option(label="Troops", description="View troops speedups")
        self.add_option(label="Research", description="View research speedups")
        self.add_option(label="Construction", description="View construction speedups")
    
    async def callback(self, interaction: discord.Interaction):
        # Display the registration details based on the selected type
        await display_registration_details(interaction, self.values[0])

class InitialChoicesSelect(discord.ui.Select):
    def __init__(self, *args, **kwargs):
        options = [
            discord.SelectOption(label="FEL", description="Choose FEL"),
            discord.SelectOption(label="FEL Academy", description="Choose FEL Academy"),
            discord.SelectOption(label="Another Alliance", description="Specify another alliance"),
            discord.SelectOption(label="Another State", description="Specify another state"),
            discord.SelectOption(label="Not Applicable", description="Not Applicable")
        ]
        super().__init__(*args, options=options, custom_id="initial_choice_select", placeholder="Choose an option...", min_values=1, max_values=1, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        logger.info(f"Initial choice selected: {choice}")
        if choice == "Not Applicable":
            not_applicable_role_id = int(os.getenv("EXTERNAL_GAME_ROLE_ID"))
            role = interaction.guild.get_role(int(not_applicable_role_id))
            member = await interaction.guild.fetch_member(interaction.user.id)
            
            if role:
                await member.add_roles(role)
                logger.info(f"Added 'Not Applicable' role to {member.display_name}")
                await interaction.response.send_message("The 'Not Applicable' role has been assigned to you.", ephemeral=True)
            else:
                logger.warning(f"Role not found: {not_applicable_role_id}")
                await interaction.response.send_message("An error occurred while assigning your role. Please contact an administrator.", ephemeral=True)
        else:
            # For other choices, ask for more details via a modal
            modal = FollowUpModal(initial_choice=choice)
            await interaction.response.send_modal(modal)

class FollowUpModal(Modal):
    def __init__(self, initial_choice, *args, **kwargs):
        kwargs['title'] = 'Further Details'
        super().__init__(*args, **kwargs)
        self.initial_choice = initial_choice

        if initial_choice in ["Another Alliance", "Another State"]:
            self.add_item(InputText(label="Alliance", placeholder="Max 3 characters", max_length=3, custom_id="alliance"))

        if initial_choice == "Another State":
            self.add_item(InputText(label="State", placeholder="Max 4 digits", max_length=4, custom_id="state"))

        self.add_item(InputText(label="In-Game Name", placeholder="Your in-game name", custom_id="ingame_name", max_length=16))

    async def callback(self, interaction: discord.Interaction):
        logger.info('Starting FollowUpModal callback')
        try:
            guild = interaction.guild
            member = await guild.fetch_member(interaction.user.id)
            if member is None:
                logger.warning("Member not found in the guild.")
                await interaction.response.send_message("Could not find your member information in this server.", ephemeral=True)
                return

            # Initialize variables to extract InputText values
            ingame_name = ""
            alliance = ""
            state = ""
            
            for item in self.children:
                if isinstance(item, InputText):  # Check if the item is an InputText component
                    if item.custom_id == "ingame_name":
                        ingame_name = item.value
                    elif item.custom_id == "alliance":
                        alliance = item.value
                    elif item.custom_id == "state":
                        state = item.value

            if self.initial_choice not in ["FEL", "FEL Academy"]:
                role_name_prefix = f"{state}-" if state else ""
                role_name = f"diplo-{role_name_prefix}{alliance.lower()}".strip()

                role = discord.utils.find(lambda r: r.name == role_name, guild.roles)
                if not role and alliance:  # Ensure there's an alliance or state specified
                    logger.info(f"Creating new role: {role_name}")
                    role = await guild.create_role(name=role_name, reason="New alliance/state role created")

                if role:
                    await member.add_roles(role)
                    logger.info(f"Role '{role_name}' has been added to {member.display_name}.")
                
                channel_name = role_name.lower()  # The channel name will be the same as the role name
                category_id = 1158968530704793640
                category = guild.get_channel(category_id)

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),  # Default role cannot access or send messages
                    role: discord.PermissionOverwrite(read_messages=True, send_messages=True),  # New role can access and send messages
                    guild.get_role(int(os.getenv("LEADERSHIP_ROLE_ID"))): discord.PermissionOverwrite(read_messages=True, send_messages=True)  # Leadership can access and send messages
                }

                channel = discord.utils.get(guild.text_channels, name=channel_name, category_id=category_id)

                channel_created = False
                # Check if the channel already exists or needs to be created
                if not channel and category:
                    channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
                    logger.info(f"Created new channel: {channel_name} under category {category.name}")
                    channel_created = True

                # Construct a welcome message
                welcome_embed = Embed(color=discord.Colour.blue())  # Set embed color to blue

                if channel_created:
                    # If the channel was just created, send a special welcome message
                    welcome_embed.description = f"Welcome to the FEL discord server, {member.mention}! We see you're the first person from {'State ' if state else ''}{alliance if alliance else 'your alliance'}, this is your alliance's personal chat with FEL leadership. Enjoy your stay!"
                    welcome_embed.title = "A Warm Welcome!"
                else:
                    # For existing channels, send a standard welcome message
                    welcome_embed.description = f"Welcome to your alliance's personal chat with FEL leadership, {member.mention}!"
                    welcome_embed.title = "Welcome!"

                # Send the welcome message in the channel
                await channel.send(embed=welcome_embed)

            # Construct the new nickname based on the initial choice and provided details
            if self.initial_choice == "FEL":
                new_nickname = f"[FEL] {ingame_name}"
            elif self.initial_choice == "FEL Academy":
                new_nickname = f"[FeL] {ingame_name}"
            elif self.initial_choice == "Another Alliance":
                new_nickname = f"[{alliance}] {ingame_name}" if alliance else ingame_name
            elif self.initial_choice == "Another State":
                new_nickname = f"#{state} [{alliance}] {ingame_name}" if state and alliance else ingame_name
            else:
                new_nickname = ingame_name  # Default case, should not happen

            # Ensure the new nickname is properly formatted
            new_nickname = new_nickname.strip()

            # Attempt to change the user's nickname
            await member.edit(nick=new_nickname)
            logger.info(f"Nickname updated to '{new_nickname}' for {member.display_name}")

            # Role assignment logic here...
            # Define role IDs for each choice
            role_ids = {
                "FEL": [int(os.getenv("GENERAL_ALLIANCE_ROLE_ID")), int(os.getenv("FEL_ALLIANCE_ROLE_ID"))],  # General and FEL role
                "FEL Academy": [int(os.getenv("GENERAL_ALLIANCE_ROLE_ID")), int(os.getenv("FEL_ACADEMY_ROLE_ID"))],  # General and FeL Academy role
                "Another Alliance": int(os.getenv("EXTERNAL_ALLIANCE_ROLE_ID")),
                "Another State": int(os.getenv("EXTERNAL_STATE_ROLE_ID")),
                "Not Applicable": int(os.getenv("EXTERNAL_GAME_ROLE_ID"))
            }

            # Fetch and assign roles based on the initial choice
            roles_to_assign = []
            if self.initial_choice in role_ids:
                if isinstance(role_ids[self.initial_choice], list):
                    for role_id in role_ids[self.initial_choice]:
                        role = guild.get_role(int(role_id))
                        if role:
                            roles_to_assign.append(role)
                else:
                    role = guild.get_role(int(role_ids[self.initial_choice]))
                    if role:
                        roles_to_assign.append(role)
            
            if roles_to_assign:
                await member.add_roles(*roles_to_assign)
                logger.info(f"Roles {' ,'.join([role.name for role in roles_to_assign])} have been added to {member.display_name}.")

            #await interaction.response.send_message("An error occurred processing your request.", ephemeral=True)
            await interaction.response.send_message(f"Thanks for being here, {member.display_name}. We've updated your roles and permissions", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in FollowUpModal callback: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred processing your request.", ephemeral=True)

class NameChangeModal(Modal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_name = InputText(label="New In-Game Name", placeholder="Enter your new in-game name here...", max_length=16)
        self.add_item(self.new_name)

    async def callback(self, interaction: discord.Interaction):
        try:
            print("On submit handler running")
            member = interaction.user
            current_nickname = member.display_name
            new_nickname = self.new_name.value  # Correctly access the input value

            # Logic to append or replace the in-game name
            if "]" in current_nickname:
                prefix = current_nickname.split("]")[0] + "]"
                new_nickname = f"{prefix} {new_nickname}"

            await member.edit(nick=new_nickname)
            await interaction.response.send_message(f"Your in-game name has been changed to {new_nickname}.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in NameChangeModal callback: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred processing your request.", ephemeral=True)

class DaysModal(Modal):
    def __init__(self, speedup_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.speedup_type = speedup_type
        self.add_item(InputText(label="Number of Days", placeholder="Enter the number of days...", custom_id="days_input"))
    
    async def callback(self, interaction):
        # Extract the number of days from the modal's input text
        days = self.children[0].value
        
        # Update the registry with the new value
        await self.update_speedup_registry(interaction.user.id, days)
        
        # Send a confirmation message
        await interaction.response.send_message(f"You have registered {days} days for {self.speedup_type}.", ephemeral=True)

    async def update_speedup_registry(self, member_id, days):
        # Define the filename based on the speedup type
        filename = f"register-{self.speedup_type}.json"
        # Check if the file exists, and load it; if not, initialize an empty dictionary
        if os.path.exists(filename):
            with open(filename, "r") as file:
                registry = json.load(file)
        else:
            registry = {}

        # Update the registry with the new days value for the member
        registry[str(member_id)] = days

        # Write the updated registry back to the file
        with open(filename, "w") as file:
            json.dump(registry, file)

class UnlockButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, label="🔓 Unlock Access", style=discord.ButtonStyle.success, custom_id="unlock_access", **kwargs)

    async def callback(self, interaction: discord.Interaction):
        # Find the member_id associated with this message_id
        message_id = interaction.message.id
        member_id = None
        for m_id, mem_id in user_message_associations:
            if m_id == message_id:
                member_id = mem_id
                break

        if member_id and interaction.user.id == member_id:
            view = InitialChoicesView()
            await interaction.response.send_message("Please choose an option:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("This button isn't for you!", ephemeral=True)

##@bot.event
##async def on_ready():
##    print(f'Logged in as {bot.user}')

@bot.event
async def on_member_update(before, after):
    # Check if the update was a role addition
    if len(before.roles) < len(after.roles):
        new_role = next(role for role in after.roles if role not in before.roles)
        # Define the role IDs that indicate registration completion
        registration_role_ids = {
            int(os.getenv("GENERAL_ALLIANCE_ROLE_ID")), 
            int(os.getenv("EXTERNAL_ALLIANCE_ROLE_ID")),
            int(os.getenv("EXTERNAL_STATE_ROLE_ID")),
            int(os.getenv("EXTERNAL_GAME_ROLE_ID"))
        }
        
        if new_role.id in registration_role_ids:
            # Search through the list of tuples for a message ID associated with this member
            associated_message_id = None
            for message_id, member_id in user_message_associations:
                if member_id == after.id:
                    associated_message_id = message_id
                    break  # Stop searching once we find a match
            
            if associated_message_id:
                channel_id = BARRICADE_CHANNEL_ID
                channel = bot.get_channel(channel_id)  # The channel where the welcome message was sent
                try:
                    # Attempt to delete the welcome message
                    msg = await channel.fetch_message(associated_message_id)
                    await msg.delete()
                    logger.info(f"Deleted welcome message for {after.display_name}")
                    # Remove the tuple from the list to clean up
                    user_message_associations.remove((associated_message_id, after.id))
                    save_associations()
                except discord.NotFound:
                    logger.info(f"Message already deleted for {after.display_name}")
                except Exception as e:
                    logger.error(f"Failed to delete welcome message for {after.display_name}: {e}")
    
    if before.nick != after.nick:
        logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
        embed = discord.Embed(title="Nickname Change for:", description=f"{after}", color=0x3498db)
        embed.add_field(name="Changed From:", value=before.nick if before.nick else "(None)", inline=False)
        embed.add_field(name="Changed To:", value=after.nick if after.nick else "(None)", inline=False)
        await logs_channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
    embed = discord.Embed(title="SERVER JOIN", description=f"{member.display_name} ({member})", color=discord.Color.green())
    await logs_channel.send(embed=embed)

    channel_id = BARRICADE_CHANNEL_ID
    channel = bot.get_channel(channel_id)

    if channel:
        # Creating the embed message
        embed = discord.Embed(title="Welcome to the Server!",
                            description=f"{member.mention}, please select an option below to continue.",
                            color=discord.Color.green())
        
        # Creating the view that holds your button
        view = discord.ui.View()
        view.add_item(UnlockButton())  # Assuming UnlockButton is your button class
        
        # Sending the embed and button together
        message = await channel.send(embed=embed, view=view)
        # Store the message ID associated with the user
        user_message_associations.append((message.id, member.id))
        save_associations()

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="SERVER LEAVE", description=f"{member.display_name} has left the server.", color=discord.Color.red())
    logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
    await logs_channel.send(embed=embed)


@bot.command(description="Sends the bot's latency.") # this decorator makes a slash command
async def ping(ctx): # a slash command will be created with the name "ping"
    await ctx.respond(f"Pong! Latency is {bot.latency}")

@bot.slash_command(guild_ids=[ALLIANCE_ID], name="resetaccess", description="Reset access for a member.")
@commands.has_role(LEADERSHIP_ROLE_ID)  # Ensure only members with the specific role can use this command
async def resetaccess(ctx: discord.ApplicationContext, member: discord.Member):
    # Clear all roles and nickname
    await member.edit(nick=None, roles=[])
    await ctx.respond(f"Access for {member.display_name} has been reset.", ephemeral=True)
    
    # Send a message to the barricade channel
    channel = bot.get_channel(BARRICADE_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="Welcome to the Server!",
                              description=f"{member.mention}, please select an option below to continue.",
                              color=discord.Color.green())
        view = discord.ui.View()
        view.add_item(UnlockButton())  # Ensure your UnlockButton is defined
        
        message = await channel.send(embed=embed, view=view)
        user_message_associations.append((message.id, member.id))
        save_associations()
    else:
        await ctx.respond("Failed to find the barricade channel.", ephemeral=True)
    
@bot.slash_command(guild_ids=[ALLIANCE_ID], name="changename", description="Change your in-game name")
async def changename(ctx):
    modal = NameChangeModal(title="Change Your Name By Filling Out Below")
    await ctx.response.send_modal(modal)

@bot.slash_command(guild_ids=[ALLIANCE_ID], name="register", description="Register your progress")
async def register(ctx):
    # Create a view to hold the select menu
    view = RegisterSelectView()
    await ctx.respond("Please select an option:", view=view, ephemeral=True)

@bot.slash_command(guild_ids=[ALLIANCE_ID], name="registration", description="View speedup registration details")
async def registration(ctx, member: Option(Member, required=False, description="Select a member")):
    # If a member is specified, show their details directly
    if member:
        await show_member_speedups(ctx, member)
    else:
        # Otherwise, present a select menu to choose the speedup type
        view = SpeedupTypeView()
        await ctx.respond("Select the type of speedups to view:", view=view, ephemeral=False)

async def display_registration_details(interaction, speedup_type):
    filename = f"register-{speedup_type.lower()}.json"
    guild = interaction.guild  # The guild (server) from the interaction
    
    try:
        with open(filename, "r") as file:
            registry = json.load(file)
    except FileNotFoundError:
        await interaction.response.send_message(f"No registrations found for {speedup_type}.", ephemeral=False)
        return
    
    member_info_list = []
    for member_id, days in registry.items():
        member = guild.get_member(int(member_id))  # Fetch the member object from the ID
        if member:
            # If member is found, use their display name
            member_name = member.display_name
        else:
            # If member not found (e.g., left the server), use a placeholder
            member_name = f"Member ID {member_id} (not found)"
        member_info_list.append((member_name, days))
    
    # Sort the list by days (descending) and take top 35
    sorted_member_info_list = sorted(member_info_list, key=lambda x: int(x[1]), reverse=True)[:35]
    formatted_list = "\n".join([f"{idx + 1}. {member_name}: {days} days" for idx, (member_name, days) in enumerate(sorted_member_info_list)])
    
    if formatted_list:
        await interaction.response.send_message(f"```{formatted_list}```", ephemeral=False)
    else:
        await interaction.followup.send("No registrations found.", ephemeral=False)

async def show_member_speedups(ctx, member):
    speedup_types = ["troops", "research", "construction"]
    member_speedups = {}

    # Iterate through each type of speedup and try to find the member's data
    for speedup_type in speedup_types:
        filename = f"register-{speedup_type}.json"
        try:
            with open(filename, "r") as file:
                registry = json.load(file)
                # If the member's ID is in the registry, add it to the member_speedups dictionary
                if str(member.id) in registry:
                    member_speedups[speedup_type] = registry[str(member.id)]
        except FileNotFoundError:
            # If the file doesn't exist, just skip it
            continue

    if member_speedups:
        # Construct the message if there are speedups registered for the member
        message_parts = [f"{speedup_type.capitalize()}: {days} days" for speedup_type, days in member_speedups.items()]
        message = f"Member {member.display_name} has:\n" + "\n".join(message_parts)
    else:
        # Default message if no speedups are found for the member
        message = f"Member {member.display_name} has no registered speedups."

    await ctx.respond(message, ephemeral=False)

bot.run(os.getenv("BOT_TOKEN"))
