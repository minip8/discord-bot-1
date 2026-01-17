from discord import Member


async def safe_direct_message(member: Member, message: str) -> Exception | None:
    """
    Returns empty string if successful, otherwise False
    """
    try:
        await member.send(message)
    except Exception as e:
        return e
