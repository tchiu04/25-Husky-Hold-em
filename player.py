from bot import Bot
from type.poker_action import PokerAction, PokerRound
from type.round_state import RoundStateClient
import random

class SimplePlayer(Bot):
    def __init__(self):
        super().__init__()
        self.starting_chips = 0
        self.hand_strength = 0
        self.position = 0
        self.aggression_factor = 1.2  # Controls how aggressive the bot is

    def on_start(self, starting_chips: int):
        self.starting_chips = starting_chips
        print(f"Player {self.id} starting with {starting_chips} chips")

    def on_round_start(self, round_state: RoundStateClient, remaining_chips: int):
        # Reset hand strength at the start of each round
        self.hand_strength = self._evaluate_hand_strength(round_state)
        print(f"Player {self.id} hand strength: {self.hand_strength}")

    def _evaluate_hand_strength(self, round_state: RoundStateClient) -> float:
        """Evaluate the strength of the current hand (0.0 to 1.0)"""
        # This is a simplified hand strength evaluation
        # In a real implementation, you would want to use proper poker hand evaluation
        if round_state.round == PokerRound.PREFLOP:
            # Preflop hand strength is based on card values and suitedness
            return random.uniform(0.3, 0.7)  # Simplified for example
        else:
            # Post-flop hand strength considers community cards
            return random.uniform(0.4, 0.9)  # Simplified for example

    def _calculate_pot_odds(self, round_state: RoundStateClient) -> float:
        """Calculate pot odds (0.0 to 1.0)"""
        amount_to_call = round_state.current_bet - round_state.player_bets[str(self.id)]
        if amount_to_call == 0:
            return 0.0
        return amount_to_call / (round_state.pot + amount_to_call)

    def _should_raise(self, round_state: RoundStateClient, remaining_chips: int) -> bool:
        """Determine if we should raise based on hand strength and situation"""
        pot_odds = self._calculate_pot_odds(round_state)
        
        # Raise if we have a strong hand and pot odds are favorable
        if self.hand_strength > 0.7 and pot_odds < 0.3:
            return True
            
        # Raise if we're in late position with a decent hand
        if round_state.current_player > 1 and self.hand_strength > 0.6:
            return True
            
        return False

    def get_action(self, round_state: RoundStateClient, remaining_chips: int):
        """Returns the action for the player."""
        amount_to_call = round_state.current_bet - round_state.player_bets[str(self.id)]
        
        # If we can check, evaluate whether to check or raise
        if amount_to_call == 0:
            if self._should_raise(round_state, remaining_chips):
                raise_amount = min(
                    round_state.pot * self.aggression_factor,
                    round_state.max_raise,
                    remaining_chips
                )
                return PokerAction.RAISE, raise_amount
            return PokerAction.CHECK, 0

        # If we need to call, evaluate whether to call, raise, or fold
        pot_odds = self._calculate_pot_odds(round_state)
        
        # Fold if hand strength is too low compared to pot odds
        if self.hand_strength < pot_odds * 1.5:
            return PokerAction.FOLD, 0
            
        # Raise if we have a strong hand and pot odds are favorable
        if self._should_raise(round_state, remaining_chips):
            raise_amount = min(
                round_state.pot * self.aggression_factor,
                round_state.max_raise,
                remaining_chips
            )
            return PokerAction.RAISE, raise_amount
            
        # Call if hand strength is reasonable compared to pot odds
        if self.hand_strength >= pot_odds:
            return PokerAction.CALL, amount_to_call
            
        # Fold if we can't justify the call
        return PokerAction.FOLD, 0

    def on_end_round(self, round_state: RoundStateClient, remaining_chips: int):
        """Called at the end of the round."""
        print(f"Player {self.id} ended round with {remaining_chips} chips")

    def on_end_game(self, round_state: RoundStateClient, score: float):
        print(f"Player {self.id} ended game with score: {score}")