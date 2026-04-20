"""
Color utility module - for terminal colored output
"""

# ANSI escape sequences
class Colors:
    """Terminal color class"""
    # Base colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Styles
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    ITALIC = "\033[3m"

    # Reset
    RESET = "\033[0m"


def color(text: str, color_code: str) -> str:
    """Add color to text"""
    return f"{color_code}{text}{Colors.RESET}"


def color_bold(text: str, color_code: str) -> str:
    """Add color and bold to text"""
    return f"{color_code}{Colors.BOLD}{text}{Colors.RESET}"


# Common color aliases
def red(text: str) -> str:
    return color(text, Colors.RED)


def green(text: str) -> str:
    return color(text, Colors.GREEN)


def yellow(text: str) -> str:
    return color(text, Colors.YELLOW)


def blue(text: str) -> str:
    return color(text, Colors.BLUE)


def magenta(text: str) -> str:
    return color(text, Colors.MAGENTA)


def cyan(text: str) -> str:
    return color(text, Colors.CYAN)


def white(text: str) -> str:
    return color(text, Colors.WHITE)


def gray(text: str) -> str:
    """Gray text (for displaying secondary info such as notes)"""
    return color(text, Colors.BRIGHT_BLACK)


def bright_red(text: str) -> str:
    return color(text, Colors.BRIGHT_RED)


def bright_green(text: str) -> str:
    return color(text, Colors.BRIGHT_GREEN)


def bright_yellow(text: str) -> str:
    return color(text, Colors.BRIGHT_YELLOW)


def bright_blue(text: str) -> str:
    return color(text, Colors.BRIGHT_BLUE)


def bright_magenta(text: str) -> str:
    return color(text, Colors.BRIGHT_MAGENTA)


def bright_cyan(text: str) -> str:
    return color(text, Colors.BRIGHT_CYAN)


def bold_red(text: str) -> str:
    return color_bold(text, Colors.RED)


def bold_green(text: str) -> str:
    return color_bold(text, Colors.GREEN)


def bold_yellow(text: str) -> str:
    return color_bold(text, Colors.YELLOW)


def bold_blue(text: str) -> str:
    return color_bold(text, Colors.BLUE)


def bold_magenta(text: str) -> str:
    return color_bold(text, Colors.MAGENTA)


def bold_cyan(text: str) -> str:
    return color_bold(text, Colors.CYAN)


# Separator and title decoration
def section_bar(title: str = "", color_code: str = Colors.CYAN) -> str:
    """Create a colored separator bar"""
    return f"\n{color_code}{'=' * 60}\n  {title}\n{'=' * 60}{Colors.RESET}\n"


def field_label(num: int, label: str, color_code: str = Colors.BRIGHT_CYAN) -> str:
    """Format field label"""
    return color(f"  {num}. {label}", color_code)


def field_value(value: str, color_code: str = Colors.WHITE) -> str:
    """Format field value"""
    return color(f"     {value}", color_code)


def header_text(text: str, color_code: str = Colors.BRIGHT_YELLOW) -> str:
    """Header text"""
    return color_bold(text, color_code)


def highlight_text(text: str, color_code: str = Colors.BRIGHT_GREEN) -> str:
    """Highlighted text"""
    return color(text, color_code)


def error_text(text: str) -> str:
    """Error text"""
    return bright_red(text)


def success_text(text: str) -> str:
    """Success text"""
    return bright_green(text)


def warning_text(text: str) -> str:
    """Warning text"""
    return bright_yellow(text)


def info_text(text: str) -> str:
    """Info text"""
    return bright_cyan(text)


# Confirmation table color scheme
CONFIRM_COLORS = {
    "title": Colors.BRIGHT_YELLOW,       # Research title - yellow
    "framework": Colors.BRIGHT_CYAN,     # Analysis framework - cyan
    "background": Colors.BRIGHT_GREEN,   # Research background - green
    "purpose": Colors.BRIGHT_MAGENTA,     # Research purpose - magenta
    "boundaries": Colors.BRIGHT_BLUE,    # Research boundaries - blue
    "questions": Colors.BRIGHT_RED,       # Research questions - red
    "header": Colors.CYAN,
    "option_confirm": Colors.GREEN,
    "option_modify": Colors.YELLOW,
    "field_num": Colors.WHITE,
}


def yellow_box(text: str, width: int = 60) -> str:
    """Wrap text in yellow box"""
    lines = text.split('\n')
    result = []

    # Top border
    result.append(f"{Colors.BRIGHT_YELLOW}{'═' * width}{Colors.RESET}")

    for line in lines:
        # Calculate padding
        padding = width - len(line) - 4  # -4 for │ and spaces
        if padding < 0:
            padding = 0
        result.append(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

    # Bottom border
    result.append(f"{Colors.BRIGHT_YELLOW}{'═' * width}{Colors.RESET}")

    return '\n'.join(result)


def yellow_box_auto(text: str, width: int = 62) -> str:
    """Auto-adjusting yellow box, calculated based on longest line"""
    lines = text.split('\n')
    # Calculate length of longest line
    max_len = max(len(line) for line in lines)
    width = max(max_len + 4, 40)  # Minimum width 40

    result = []

    # Top border
    result.append(f"{Colors.BRIGHT_YELLOW}╔{'═' * (width - 2)}╗{Colors.RESET}")

    for line in lines:
        padding = width - len(line) - 4
        if padding < 0:
            padding = 0
        result.append(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

    # Bottom border
    result.append(f"{Colors.BRIGHT_YELLOW}╚{'═' * (width - 2)}╝{Colors.RESET}")

    return '\n'.join(result)


def section_box(title: str, content_lines: list, width: int = 62) -> str:
    """Create yellow box with title and content"""
    result = []

    # Calculate max width
    max_len = max(len(title), max(len(line) if line else 0 for line in content_lines))
    width = max(max_len + 4, 40)

    # Top
    result.append(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (width - 2)}╗{Colors.RESET}")

    # Title row (centered)
    title_padding = (width - 2 - len(title)) // 2
    result.append(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{' ' * title_padding}{Colors.BOLD}{Colors.YELLOW}{title}{Colors.RESET}{' ' * (width - 2 - title_padding - len(title))}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")

    # Separator line
    result.append(f"{Colors.BRIGHT_YELLOW}╠{'═' * (width - 2)}╣{Colors.RESET}")

    # Content lines
    for line in content_lines:
        padding = width - len(line) - 4
        if padding < 0:
            padding = 0
        result.append(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

    # Bottom
    result.append(f"{Colors.BRIGHT_YELLOW}╚{'═' * (width - 2)}╝{Colors.RESET}")

    return '\n'.join(result)