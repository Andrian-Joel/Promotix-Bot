import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "data.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Data helpers ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_guild_data(guild_id: int):
    data = load_data()
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {"ladder": [], "log_channel": None}
        save_data(data)
    return data[gid]

def update_guild_data(guild_id: int, new_data: dict):
    data = load_data()
    data[str(guild_id)] = new_data
    save_data(data)

# ---------- Helpers ----------
def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

def can_manage(interaction: discord.Interaction, role: discord.Role) -> bool:
    if not interaction.guild:
        return False
    if not interaction.user.guild_permissions.manage_roles:
        return False
    bot_top = interaction.guild.me.top_role
    if role >= bot_top:
        return False
    if isinstance(interaction.user, discord.Member) and role >= interaction.user.top_role:
        return False
    return True

async def send_log(guild: discord.Guild, embed: discord.Embed):
    gdata = get_guild_data(guild.id)
    if gdata.get("log_channel"):
        channel = guild.get_channel(gdata["log_channel"])
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

# ---------- Events ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        guild = discord.Object(id=1407696419082731621)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to your server")
    except Exception as e:
        print(f"Sync failed: {e}")

# ---------- Commands ----------
@bot.tree.command(name="promote", description="Promote a member to a specific role")
@app_commands.describe(member="Member to promote", role="Role to give", reason="Reason for promotion")
async def promote(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str):
    if not can_manage(interaction, role):
        await interaction.response.send_message("❌ You or the bot cannot manage that role.", ephemeral=True)
        return
    if role in member.roles:
        await interaction.response.send_message(f"{member.mention} already has {role.mention}.", ephemeral=True)
        return

    try:
        await member.add_roles(role, reason=f"Promoted by {interaction.user}: {reason}")
        await interaction.response.send_message(f"✅ **Promoted** {member.mention} → {role.mention}\n**Reason:** {reason}")

        embed = discord.Embed(title="🔼 Promotion", color=discord.Color.green())
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="New Role", value=role.mention, inline=True)
        embed.add_field(name="By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await send_log(interaction.guild, embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)

@bot.tree.command(name="demote", description="Demote a member from a specific role")
@app_commands.describe(member="Member to demote", role="Role to remove", reason="Reason for demotion")
async def demote(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str):
    if not can_manage(interaction, role):
        await interaction.response.send_message("❌ You or the bot cannot manage that role.", ephemeral=True)
        return
    if role not in member.roles:
        await interaction.response.send_message(f"{member.mention} does not have {role.mention}.", ephemeral=True)
        return

    try:
        await member.remove_roles(role, reason=f"Demoted by {interaction.user}: {reason}")
        await interaction.response.send_message(f"✅ **Demoted** {member.mention} — removed {role.mention}\n**Reason:** {reason}")

        embed = discord.Embed(title="🔽 Demotion", color=discord.Color.orange())
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Removed Role", value=role.mention, inline=True)
        embed.add_field(name="By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await send_log(interaction.guild, embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)

@bot.tree.command(name="rankup", description="Promote a member one step up the rank ladder")
@app_commands.describe(member="Member to rank up", reason="Reason")
async def rankup(interaction: discord.Interaction, member: discord.Member, reason: str):
    gdata = get_guild_data(interaction.guild.id)
    ladder = gdata.get("ladder", [])
    if not ladder:
        await interaction.response.send_message("❌ No rank ladder set. Use `/setladder` first.", ephemeral=True)
        return

    current_index = -1
    for i, role_id in enumerate(ladder):
        role = interaction.guild.get_role(role_id)
        if role and role in member.roles:
            current_index = i

    if current_index == len(ladder) - 1:
        await interaction.response.send_message(f"{member.mention} is already at the highest rank.", ephemeral=True)
        return

    next_index = current_index + 1
    next_role = interaction.guild.get_role(ladder[next_index])
    if not next_role or not can_manage(interaction, next_role):
        await interaction.response.send_message("❌ Cannot manage the next role.", ephemeral=True)
        return

    roles_to_remove = [interaction.guild.get_role(rid) for rid in ladder if interaction.guild.get_role(rid) in member.roles]
    try:
        if roles_to_remove:
            await member.remove_roles(*[r for r in roles_to_remove if r], reason=f"Rank up by {interaction.user}")
        await member.add_roles(next_role, reason=f"Rank up by {interaction.user}: {reason}")

        await interaction.response.send_message(f"✅ **Rank Up!** {member.mention} → {next_role.mention}\n**Reason:** {reason}")

        embed = discord.Embed(title="⬆️ Rank Up", color=discord.Color.blue())
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="New Rank", value=next_role.mention, inline=True)
        embed.add_field(name="By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await send_log(interaction.guild, embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permission error.", ephemeral=True)

@bot.tree.command(name="rankdown", description="Demote a member one step down the rank ladder")
@app_commands.describe(member="Member to rank down", reason="Reason")
async def rankdown(interaction: discord.Interaction, member: discord.Member, reason: str):
    gdata = get_guild_data(interaction.guild.id)
    ladder = gdata.get("ladder", [])
    if not ladder:
        await interaction.response.send_message("❌ No rank ladder set.", ephemeral=True)
        return

    current_index = -1
    for i, role_id in enumerate(ladder):
        role = interaction.guild.get_role(role_id)
        if role and role in member.roles:
            current_index = i

    if current_index <= 0:
        await interaction.response.send_message(f"{member.mention} is already at the lowest rank.", ephemeral=True)
        return

    prev_role = interaction.guild.get_role(ladder[current_index - 1])
    current_role = interaction.guild.get_role(ladder[current_index])

    if not prev_role or not can_manage(interaction, current_role):
        await interaction.response.send_message("❌ Cannot manage roles.", ephemeral=True)
        return

    try:
        await member.remove_roles(current_role, reason=f"Rank down by {interaction.user}")
        await member.add_roles(prev_role, reason=f"Rank down by {interaction.user}: {reason}")

        await interaction.response.send_message(f"✅ **Rank Down** {member.mention} → {prev_role.mention}\n**Reason:** {reason}")

        embed = discord.Embed(title="⬇️ Rank Down", color=discord.Color.dark_orange())
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="New Rank", value=prev_role.mention, inline=True)
        embed.add_field(name="By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await send_log(interaction.guild, embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permission error.", ephemeral=True)

@bot.tree.command(name="ranks", description="Show the current rank ladder")
async def ranks(interaction: discord.Interaction):
    gdata = get_guild_data(interaction.guild.id)
    ladder = gdata.get("ladder", [])
    if not ladder:
        await interaction.response.send_message("No rank ladder set yet. Use `/setladder`.", ephemeral=True)
        return

    lines = []
    for i, role_id in enumerate(ladder, 1):
        role = interaction.guild.get_role(role_id)
        name = role.mention if role else f"`Deleted Role`"
        lines.append(f"**{i}.** {name}")

    embed = discord.Embed(title="Rank Ladder", description="\n".join(lines), color=discord.Color.blurple())
    embed.set_footer(text="Lowest → Highest")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setladder", description="Set the rank ladder (lowest to highest)")
@app_commands.describe(roles="Mention the roles in order from lowest to highest")
async def setladder(interaction: discord.Interaction, roles: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Only admins can use this.", ephemeral=True)
        return

    role_ids = []
    for word in roles.split():
        if word.startswith("<@&") and word.endswith(">"):
            try:
                rid = int(word[3:-1])
                if interaction.guild.get_role(rid):
                    role_ids.append(rid)
            except:
                continue

    if len(role_ids) < 2:
        await interaction.response.send_message("❌ Provide at least 2 valid role mentions.", ephemeral=True)
        return

    gdata = get_guild_data(interaction.guild.id)
    gdata["ladder"] = role_ids
    update_guild_data(interaction.guild.id, gdata)

    mentions = [interaction.guild.get_role(rid).mention for rid in role_ids]
    await interaction.response.send_message("✅ Rank ladder set:\n" + " → ".join(mentions))

@bot.tree.command(name="setlog", description="Set the channel for promotion logs")
@app_commands.describe(channel="The log channel")
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Only admins can use this.", ephemeral=True)
        return

    gdata = get_guild_data(interaction.guild.id)
    gdata["log_channel"] = channel.id
    update_guild_data(interaction.guild.id, gdata)
    await interaction.response.send_message(f"✅ Logs will be sent to {channel.mention}")

@bot.tree.command(name="clearladder", description="Clear the rank ladder")
async def clearladder(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Only admins can use this.", ephemeral=True)
        return

    gdata = get_guild_data(interaction.guild.id)
    gdata["ladder"] = []
    update_guild_data(interaction.guild.id, gdata)
    await interaction.response.send_message("✅ Rank ladder cleared.")

@bot.tree.command(name="createrole", description="Create a new role (Admin only)")
@app_commands.describe(name="Name of the new role", color="Hex color (example: #ff0000) - optional")
async def createrole(interaction: discord.Interaction, name: str, color: str = None):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Only admins can use this.", ephemeral=True)
        return

    colour = discord.Color.default()
    if color:
        try:
            colour = discord.Color.from_str(color)
        except:
            await interaction.response.send_message("❌ Invalid color. Use format like #ff0000", ephemeral=True)
            return

    try:
        new_role = await interaction.guild.create_role(name=name, colour=colour, reason=f"Created by {interaction.user}")
        await interaction.response.send_message(f"✅ Created role {new_role.mention}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="deleterole", description="Delete a role (Admin only)")
@app_commands.describe(role="The role to delete")
async def deleterole(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Only admins can use this.", ephemeral=True)
        return

    if role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ I cannot delete a role higher than or equal to my highest role.", ephemeral=True)
        return

    try:
        await role.delete(reason=f"Deleted by {interaction.user}")
        await interaction.response.send_message(f"✅ Deleted role **{role.name}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# ---------- Run ----------
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN is missing!")
    bot.run(TOKEN)