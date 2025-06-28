"""
Defines the Card class for the Memory Match Game.
"""
class Card:
    """Represents a single card for the Memory Match game."""
    def __init__(self, symbol, category=None, position=None, is_joker=False, back_symbol="🎴"):
        """
        Initialize a new card.
        
        Args:
            symbol (str): The emoji or symbol on the card face
            category (str, optional): The category this card belongs to
            position (tuple, optional): The (row, col) position on the board
            is_joker (bool, optional): Whether this card is a joker
            back_symbol (str, optional): The symbol to show when card is face down
        """
        self.symbol = symbol
        self.category = category
        self.position = position  # (row, col) tuple
        self.is_matched = False
        self.is_revealed = False  # If currently revealed in a turn
        self.is_joker = is_joker
        self.back_symbol = back_symbol
        self.joker_revealed = False  # Track if this card was revealed by a joker

    def get_display(self, force_reveal=False):
        """
        Returns the symbol to display based on state.
        
        Args:
            force_reveal (bool, optional): Force the card to be revealed
            
        Returns:
            str: The symbol to display
        """
        if self.is_matched or self.is_revealed or force_reveal:
            return self.symbol
        else:
            return self.back_symbol

    def __str__(self):
        """String representation."""
        return self.symbol

    def __repr__(self):
        """Developer representation."""
        return f"Card(symbol='{self.symbol}', category='{self.category}', position={self.position})"

    def matches(self, other_card, match_type="exact"):
        """
        Checks if this card matches another card based on match type.
        
        Args:
            other_card (Card): The card to compare with
            match_type (str, optional): The type of match to check:
                - "exact": Cards must have the same symbol
                - "category": Cards must be from the same category
                - "any": Any two cards match (for easy mode)
                
        Returns:
            bool: True if the cards match, False otherwise
        """
        if not isinstance(other_card, Card):
            return False
        if self == other_card:  # Cannot match itself (same object)
            return False

        # Special joker handling - jokers don't create permanent matches
        if self.is_joker or other_card.is_joker:
            return False

        if match_type == "any":
            # Easy: Match any two cards (just find pairs)
            return True
        elif match_type == "category":
            # Medium: Match cards from same category
            return self.category == other_card.category
        elif match_type == "exact":
            # Hard: Match exact same symbol
            return self.symbol == other_card.symbol
        else:
            return False

    def __eq__(self, other):
        """
        Checks if two Card objects are the same.
        
        Args:
            other: The object to compare with
            
        Returns:
            bool: True if the cards are equal, False otherwise
        """
        if not isinstance(other, Card):
            return NotImplemented
        # Two cards are equal if they have the same symbol and position
        return (self.symbol == other.symbol and 
                self.position == other.position)

    def __hash__(self):
        """
        Allows cards to be used in sets/dictionaries.
        
        Returns:
            int: Hash value for the card
        """
        return hash((self.symbol, self.position))
        
    def handle_joker_interaction(self, other_card):
        """
        Handles the special interaction when a joker card is revealed.
        
        Args:
            other_card (Card): The non-joker card that was revealed with the joker
            
        Returns:
            bool: True if the interaction was handled, False otherwise
        """
        if not self.is_joker and not other_card.is_joker:
            return False
            
        # Determine which card is the joker
        joker_card = self if self.is_joker else other_card
        normal_card = other_card if self.is_joker else self
        
        # Mark the normal card as temporarily revealed by a joker
        normal_card.joker_revealed = True
        
        # Both cards should be revealed for display purposes
        joker_card.is_revealed = True
        normal_card.is_revealed = True
        
        return True
    
    def reset_after_joker(self):
        """
        Resets a card's state after a joker interaction.
        
        Returns:
            bool: True if the card was affected by a joker, False otherwise
        """
        if self.joker_revealed:
            self.is_revealed = False
            self.joker_revealed = False
            return True
        return False
