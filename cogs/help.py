from discord.ext import commands

class HelpCog(commands.Cog):
    pass

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
