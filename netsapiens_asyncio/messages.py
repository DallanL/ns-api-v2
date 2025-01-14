import aiohttp
import logging
import re
from typing import Optional, Union
from .auth import NetsapiensAPI


class MessageAPI:
    def __init__(self, auth_client: NetsapiensAPI, log_level=logging.INFO):
        """
        Initialize the MessageAPI class with authentication details and logging setup.

        :param auth_client: Instance of NetsapiensAPI for managing authentication.
        :param log_level: Logging level (default is INFO).
        """
        self.auth_client = auth_client
        self.auth_data = self.auth_client.token_data
        self.base_url = self.auth_data.get("api_url") if self.auth_data else None
        self.domain = "~"
        self.user = "~"

        # Create a dedicated logger for this class
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(log_level)

        # Add a handler if the logger has no handlers (to avoid duplicate logs)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.logger.debug("MessageAPI initialized with auth client")

    async def send_message(
        self,
        message_type: str,
        message: str,
        destination: Union[str, list],
        from_number: str,
        messagesession: Optional[str] = None,  # New optional parameter
        data: Optional[str] = None,
        mime_type: Optional[str] = None,
        size: Optional[int] = None,
    ):
        """
        Send a message via the API, either to a new session or an existing session.

        :param message_type: Type of message to send (e.g., sms, mms).
        :param message: The text of the message to be sent.
        :param destination: A single recipient (str) or a list of recipients (List[str]).
        :param from_number: Sender's phone number (required for SMS).
        :param messagesession: Optional session ID to send the message in. If provided,
                               must be at least 32 characters long, alphanumeric, and underscores.
        :param data: Base64-encoded data for MMS or media chat.
        :param mime_type: Mime type of the media file for MMS or media chat.
        :param size: Size of the media file in bytes for MMS or media chat.
        :return: API response as a dictionary.
        """
        # Check and refresh token if necessary
        self.auth_data = await self.auth_client.check_token_expiry()
        self.base_url = self.auth_data.get("api_url")

        # Validate the messagesession if provided
        if messagesession:
            if not re.match(r"^[a-zA-Z0-9_]{32,}$", messagesession):
                self.logger.error("Invalid messagesession ID format.")
                raise ValueError(
                    "Invalid messagesession ID. Must be at least 32 characters long, alphanumeric, and underscores only."
                )
            # Use the session in the URL if provided
            url = f"{self.base_url}/ns-api/v2/domains/{self.domain}/users/{self.user}/messagesessions/{messagesession}/messages"
        else:
            # Use the default new message URL
            url = f"{self.base_url}/ns-api/v2/domains/{self.domain}/users/{self.user}/messages"

        # Prepare the payload
        payload = {
            "type": message_type,
            "message": message,
            "destination": (
                destination if isinstance(destination, list) else [destination]
            ),
            "from-number": from_number,
        }

        # Add optional parameters if applicable
        if data:
            payload["data"] = data
        if mime_type:
            payload["mime-type"] = mime_type
        if size:
            payload["size"] = str(size)

        self.logger.debug(f"Sending message with payload: {payload}")

        # Make the POST request
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.auth_data['access_token']}"}
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info(f"Message sent successfully: {result}")
                    return result
                else:
                    error_message = await response.text()
                    self.logger.error(f"Failed to send message: {error_message}")
                    raise Exception(f"Failed to send message: {error_message}")

    async def get_messages(
        self,
        messagesession: Optional[str] = None,
        domain: str = "~",
        user: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        """
        Retrieve message sessions or messages for a specific session.

        :param messagesession: Optional session ID to retrieve messages for. If None, retrieves all message sessions.
        :param domain: Domain to retrieve messages from. Defaults to "~" (current domain).
        :param user: Optional user to retrieve messages for. If None, retrieves all sessions for the domain.
        :param limit: Optional limit on the number of items to retrieve.
        :return: A list of dictionaries representing message sessions or messages.
        """
        # Check and refresh token if necessary
        self.auth_data = await self.auth_client.check_token_expiry()
        self.base_url = self.auth_data.get("api_url")

        # Validate messagesession if provided
        if messagesession:
            # URL for retrieving messages in a specific session
            url = f"{self.base_url}/ns-api/v2/domains/{domain}/users/{user or '~'}/messagesessions/{messagesession}/messages"
        else:
            # URL for retrieving all message sessions
            if user:
                url = f"{self.base_url}/ns-api/v2/domains/{domain}/users/{user}/messagesessions"
            else:
                url = f"{self.base_url}/ns-api/v2/domains/{domain}/messagesessions"

        # Prepare query parameters
        params = {}
        if limit:
            params["limit"] = str(limit)

        self.logger.debug(f"Retrieving messages from {url} with params: {params}")

        # Make the GET request
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.auth_data['access_token']}"}
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.logger.info(f"Messages retrieved successfully from {url}.")
                        return result
                    else:
                        error_message = await response.text()
                        self.logger.error(
                            f"Failed to retrieve messages from {url}. "
                            f"Status: {response.status}, Error: {error_message}"
                        )
                        raise Exception(
                            f"Failed to retrieve messages. Status: {response.status}, Error: {error_message}"
                        )
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error while retrieving messages: {e}")
            raise Exception("Network error occurred while retrieving messages.") from e
        except Exception as e:
            self.logger.error(f"Unexpected error while retrieving messages: {e}")
            raise Exception("An unexpected error occurred.") from e
