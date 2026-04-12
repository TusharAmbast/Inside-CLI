from rich.progress import (
    Progress, BarColumn, TextColumn,
    TimeElapsedColumn, TimeRemainingColumn, Task
)
from rich.color import Color
from rich.text import Text
import time

class GradientBarColumn(BarColumn):
    def render(self, task: Task) -> Text:
        """Custom bar with cyan-to-magenta gradient"""
        bar_width = self.bar_width or 40
        if task.total is None:
            return Text("", style="bar.back")
        
        completed_width = int((task.completed / task.total) * bar_width)
        remaining_width = bar_width - completed_width
        
        # Create gradient
        bar_text = Text()
        for i in range(completed_width):
            # Interpolate between cyan and magenta
            t = i / max(1, bar_width - 1)
            r = int(0 + t * (255 - 0))      # cyan to magenta red
            g = int(255 + t * (0 - 255))    # cyan to magenta green  
            b = int(255 + t * (255 - 255))  # cyan to magenta blue
            
            color = f"#{r:02x}{g:02x}{b:02x}"  
            bar_text.append("█", style=color)
        
        # Add remaining empty space
        bar_text.append(" " * remaining_width, style="bar.back")
        return bar_text

if __name__ == "__main__":
    with Progress(
        # TextColumn("[bold blue]Working"),
        GradientBarColumn(bar_width=50),
        # TextColumn("{task.percentage:>3.0f}%"),
        # TimeElapsedColumn(),
        # TimeRemainingColumn(),
    ) as progress:

        task_id = progress.add_task("work", total=4)
        for _ in range(4):
            time.sleep(0.5)
            progress.update(task_id, advance=1)
