import json
import socket
import logging
from typing import Optional, Any

from type.utils import get_message_type_name

from config import START_MONEY
from type.message import MessageType
from type.round_state import RoundStateClient

class Runner:
    """
    Client runner that connects to a poker server and handles the game flow.
    """
    def __init__(self, host: str, port: int,  result_path: str, sim: bool = False) -> None:
        """
        Initialize the runner with connection details.
        
        Args:
            host: Server hostname or IP address
            port: Server port
        """
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bot = None
        self.current_round: Optional[RoundStateClient] = None
        self.player_id = None
        self.logger = self._setup_logger()
        self.player_money = START_MONEY

        self.run_success = False
        self.points = 0
        self.result_path = result_path

        # Simulation mode
        self.sim = sim


    @staticmethod
    def _setup_logger():
        """Set up logging configuration."""
        logger = logging.getLogger('PokerRunner')
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        return logger
    
    def get_score(self) -> int:
        """
        Get the score of the player.
        
        Returns:
            int: Player's score
        """
        return self.points

    def set_bot(self, bot):
        """
        Set the bot instance that will play the game.
        
        Args:
            bot: Instance of a poker-playing bot
        """
        self.bot = bot

    def _process_message(self, json_message: dict) -> None:
        """
        Process a single JSON message from the server.
        
        Args:
            json_message: Parsed JSON message from server
        """
        message_type = json_message.get('type')
        message = json_message.get('message')
        
        if message_type is None:
            self.logger.error("Invalid message: missing type")
            return
            
        message_type_name = get_message_type_name(message_type)
        self.logger.info(f"Received message type: {message_type_name}")
        
        handlers = {
            MessageType.CONNECT.value: self._handle_connect,
            MessageType.GAME_START.value: self._handle_game_start,
            MessageType.GAME_STATE.value: self._handle_game_state,
            MessageType.ROUND_START.value: self._handle_round_start,
            MessageType.REQUEST_PLAYER_ACTION.value: self._handle_request_action,
            MessageType.ROUND_END.value: self._handle_round_end,
            MessageType.GAME_END.value: self._handle_game_end,
            MessageType.MESSAGE.value: self._handle_txt,  # Ignore generic messages
        }
        
        handler = handlers.get(message_type)
        if handler:
            handler(message)
        else:
            self.logger.warning(f"No handler for message type: {message_type}")

    def _handle_txt(self, message: Any) -> None:
        """Handle text message."""
        self.logger.info(f"Server: {message}")

    def _handle_connect(self, message: Any) -> None:
        """Handle connection confirmation message."""
        self.player_id = message
        self.bot.set_id(self.player_id)
        self.logger.info(f"Connected with player ID: {self.player_id}")

    def _handle_game_start(self, _: Any) -> None:
        """Handle game start message."""
        if self.bot:
            self.bot.on_start(self.player_money)
        self.logger.info("Game started")

    def _handle_game_state(self, message: dict) -> None:
        """Update current game state."""
        self.current_round = RoundStateClient(
            round=message['round'],
            round_num=message['round_num'],
            community_cards=message['community_cards'],
            pot=message['pot'],
            current_player=message['current_player'],
            current_bet=message['current_bet'],
            player_bets=message['player_bets'],
            player_actions=message['player_actions'],
            min_raise=message['min_raise'],
            max_raise=message['max_raise'],
        )
        self.logger.debug(f"Updated game state: round {message['round_num']}")

    def _handle_round_start(self, _: Any) -> None:
        """Handle round start message."""
        if self.bot and self.current_round:
            self.bot.on_round_start(self.current_round, self.player_money)
        self.logger.info(f"Round {self.current_round.round_num if self.current_round else 'unknown'} started")

    def _handle_request_action(self, _: Any) -> None:
        """Handle request for player action."""
        if not self.bot or not self.current_round:
            self.logger.error("Can't get action: bot or round state not initialized")
            return
            
        action, amount = self.bot.get_action(self.current_round, self.player_money)
        self.logger.info(f"Bot action: {action.name}, amount: {amount}")
        ok = self._validate_action(action.value, amount)
        if not ok:
            self.logger.error("Invalid action or amount")
            # punish the bot for invalid action
            self.send_action_to_server(self.player_id, 1, 0)  # fold
            return
        self.send_action_to_server(self.player_id, action.value, amount)
        self.player_money -= amount

    def _handle_round_end(self, _: Any) -> None:
        """Handle round end message."""
        if self.bot and self.current_round:
            self.bot.on_end_round(self.current_round, self.player_money)
        self.logger.info("Round ended")

    def _handle_game_end(self, message: Any) -> None:
        """Handle game end message."""
        if self.bot and self.current_round:
            self.bot.on_end_game(self.current_round, message)
            if not self.sim:
                self.append_to_file(self.result_path, str(message))
            self.points = int(message)
            self.run_success = True
        self.logger.info("Game ended")
        self.close()

    def handle_messages(self, message_data: str) -> None:
        """
        Process raw message data from the server.
        
        Args:
            message_data: Raw message string from server
        """
        lines = message_data.split('\n')
        for line in lines:
            if not line:  # Skip empty lines
                continue
                
            try:
                json_message = json.loads(line)
                self._process_message(json_message)
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding message: {line}")
            except Exception as e:
                self.logger.exception(f"Error processing message: {e}")

    def _validate_action(self, action: int, amount: int) -> bool:

        """
        Validate the action and amount before sending to server.
        
        Args:
            action: Action code (from MessageType enum)
            amount: Bet amount

        """

        if amount < 0:
            self.logger.error("Invalid amount: cannot be negative")
            return False
        
        if amount > self.player_money:
            self.logger.error("Invalid amount: exceeds player money")

        # fold
        if action == 1:
            return True
        
        # check
        if action == 2:
            if self.current_round and self.current_round.current_bet == 0:
                return True
            else:
                self.logger.error("Invalid check action: current bet is not zero")
                return False

        # call    
        if action == 3:
            needed_call = self.current_round.current_bet - self.current_round.player_bets[str(self.player_id)]
            if self.current_round and amount == needed_call and needed_call > 0:
                return True
            else:
                self.logger.error("Invalid call action: amount does not match current bet")
                return False
            
        # raise
        if action == 4:
            actual_raise = amount + self.current_round.player_bets[str(self.player_id)]

            if self.current_round and actual_raise >= self.current_round.current_bet:
                return True
            else:
                self.logger.error("Invalid raise action: amount out of range")
                return False
            
        # all in
        if action == 5:
            if self.current_round and amount == self.player_money:
                return True
            else:
                self.logger.error("Invalid all-in action: amount does not match player money")
                return False
            
        

    def send_action_to_server(self, player_id: str, action: int, amount: int) -> None:
        """
        Send player action to the server.
        
        Args:
            player_id: The ID of the player
            action: Action code (from MessageType enum)
            amount: Bet amount
        """
        message = {
            'type': MessageType.PLAYER_ACTION.value,
            'message': {
                'player_id': player_id,
                'action': action,
                'amount': amount
            }
        }

        try:
            self.client_socket.send(json.dumps(message).encode('utf-8'))
            self.logger.debug(f"Sent action: {action}, amount: {amount}")
        except Exception as e:
            self.logger.error(f"Failed to send action: {e}")

    def receive_messages(self) -> None:
        """Continuously receive messages from the server."""
        buffer = ""
        
        while True:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    self.logger.info("Server closed connection")
                    break
                    
                buffer += data
                
                # Handle potentially multiple messages in the buffer
                self.handle_messages(buffer)
                buffer = ""  # Clear buffer after processing
                
            except socket.error as e:
                self.logger.error(f"Socket error: {e}")
                break
            except Exception as e:
                self.logger.exception(f"Error receiving message: {e}")
                break

    def connect(self) -> bool:
        """
        Connect to the poker server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client_socket.connect((self.host, self.port))
            self.logger.info(f"Connected to server at {self.host}:{self.port}")
            return True
        except socket.error as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    def run(self) -> None:
        """Run the client, connecting to server and handling messages."""
        if not self.bot:
            self.logger.error("No bot set. Use set_bot() before running.")
            return
            
        if not self.connect():
            return
            
        try:
            self.receive_messages()
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            self.close()

    def append_to_file(self, filename: str, data: str) -> None:
        """Append data to a file."""
        try:
            with open(filename, 'a') as file:
                file.write(data + '\n')
            self.logger.info(f"Data appended to {filename}")
        except Exception as e:
            self.logger.error(f"Error writing to file {filename}: {e}")

    def close(self) -> None:
        """Close the connection to the server."""
        try:
            self.client_socket.close()
            self.logger.info("Connection closed")
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")