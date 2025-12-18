from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

logger = logging.getLogger(__name__)

def send_error_message(channel, token, test_name, error_details):
    """
    Sends an error alert to a specified Slack channel.
    
    Args:
        channel (str): The Slack channel name (e.g., 'logging' or '#logging').
        token (str): The Slack Bot User OAuth Token.
        test_name (str): The name of the current test context.
        error_details (str): The actual error message or exception string.
    """
    client = WebClient(token=token)
    
    text = f"🚨 *Monitor Alert* 🚨\n*Test:* {test_name}\n*Error:* {error_details}"
    
    try:
        response = client.chat_postMessage(channel=channel, text=text)
        return response
    except SlackApiError as e:
        logger.error(f"Slack API Error: {e.response['error']}")
        return None