"""
ASCII Animation (.asciimtn) file loader.

Parses .asciimtn JSON files and renders frames as terminal-compatible strings.
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple


class ASCIImtnFrame:
    """Represents a single frame from an ASCII animation."""

    def __init__(self, width: int, height: int, data: Dict[str, Dict]):
        """
        Initialize a frame.
        
        Args:
            width: Canvas width
            height: Canvas height
            data: Dictionary of coordinate -> {char, color, bgColor}
        """
        self.width = width
        self.height = height
        self.data = data

    def render(self) -> str:
        """
        Render frame as a string (plain text, no ANSI codes).
        
        Textual will handle coloring through its own styling system.
        
        Returns:
            Multi-line string with characters positioned on canvas
        """
        # Create empty canvas
        canvas = [[' ' for _ in range(self.width)] for _ in range(self.height)]

        # Place characters from data
        for coord_str, char_data in self.data.items():
            try:
                x, y = map(int, coord_str.split(','))
                if 0 <= x < self.width and 0 <= y < self.height:
                    char = char_data.get('char', ' ')
                    canvas[y][x] = char
            except (ValueError, IndexError):
                pass

        # Convert to string (plain text, no ANSI codes)
        lines = []
        for row in canvas:
            line = ''.join(row).rstrip()
            lines.append(line)
        
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        
        # Remove leading empty lines
        while lines and not lines[0]:
            lines.pop(0)
        
        return '\n'.join(lines)


class ASCIImtnAnimation:
    """Represents a complete ASCII animation."""

    def __init__(self, file_path: Path):
        """
        Load and parse an .asciimtn file.
        
        Args:
            file_path: Path to .asciimtn JSON file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.width = self.data['canvas']['width']
        self.height = self.data['canvas']['height']
        self.frame_rate = self.data['timeline']['frameRate']
        self.looping = self.data['timeline']['looping']

        # Extract frames from first layer
        self.frames: List[ASCIImtnFrame] = []
        if self.data['layers']:
            layer = self.data['layers'][0]
            for content_frame in layer.get('contentFrames', []):
                frame_data = content_frame.get('data', {})
                frame = ASCIImtnFrame(self.width, self.height, frame_data)
                self.frames.append(frame)

    def get_frame(self, index: int) -> ASCIImtnFrame:
        """
        Get a frame by index (with wrapping if looping).
        
        Args:
            index: Frame index
        
        Returns:
            ASCIImtnFrame
        """
        if not self.frames:
            return ASCIImtnFrame(self.width, self.height, {})
        
        if self.looping:
            return self.frames[index % len(self.frames)]
        return self.frames[min(index, len(self.frames) - 1)]

    def get_frame_count(self) -> int:
        """Return total number of frames."""
        return len(self.frames)


def load_asciimtn(file_path: Path) -> ASCIImtnAnimation:
    """
    Load an .asciimtn animation file.
    
    Args:
        file_path: Path to .asciimtn file
    
    Returns:
        ASCIImtnAnimation object
    """
    return ASCIImtnAnimation(file_path)
