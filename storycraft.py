#!/usr/bin/env python3
"""
StoryCraft: AI Story Generator - User-Friendly Version
A streamlined story generation tool that focuses on user prompts first

Features:
- Prompt-first approach - just describe what you want
- Intelligent parameter extraction from user descriptions
- Smart follow-up questions only when needed
- Quick story generation with minimal friction
- Story saving and library management
"""

import os
import json
import logging
import argparse
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown


@dataclass
class StoryConfig:
    """Configuration class for story generation parameters"""
    genre: str = "general"
    style: str = "narrative"
    length: str = "medium"
    tone: str = "neutral"
    protagonist: str = ""
    setting: str = ""
    theme: str = ""
    original_prompt: str = ""


class PromptAnalyzer:
    """Analyzes user prompts to extract story parameters"""
    
    def __init__(self):
        self.genre_keywords = {
            "fantasy": ["magic", "wizard", "dragon", "fairy", "enchanted", "spell", "mythical", "magical", "fantasy"],
            "sci-fi": ["space", "alien", "robot", "future", "technology", "spaceship", "laser", "cyborg", "sci-fi", "science fiction"],
            "mystery": ["detective", "murder", "clue", "investigation", "suspect", "crime", "mystery", "solve"],
            "horror": ["scary", "ghost", "monster", "haunted", "nightmare", "terror", "horror", "frightening"],
            "romance": ["love", "romance", "dating", "relationship", "wedding", "romantic", "heart", "couple"],
            "adventure": ["journey", "quest", "explore", "adventure", "treasure", "expedition", "travel"],
            "thriller": ["chase", "escape", "danger", "suspense", "thriller", "action", "pursuit"],
            "historical": ["medieval", "ancient", "historical", "century", "war", "kingdom", "empire"],
            "comedy": ["funny", "humor", "laugh", "joke", "comedy", "hilarious", "amusing"],
            "contemporary": ["modern", "today", "current", "realistic", "everyday"]
        }
        
        self.length_keywords = {
            "short": ["short", "brief", "quick", "flash", "micro"],
            "medium": ["medium", "regular", "standard"],
            "long": ["long", "detailed", "extended", "comprehensive"],
            "epic": ["epic", "saga", "massive", "huge", "enormous"]
        }
        
        self.tone_keywords = {
            "dark": ["dark", "grim", "serious", "somber", "tragic"],
            "light": ["light", "cheerful", "happy", "optimistic", "bright"],
            "humorous": ["funny", "humorous", "comedic", "amusing", "witty"],
            "dramatic": ["dramatic", "intense", "emotional", "powerful"],
            "mysterious": ["mysterious", "enigmatic", "cryptic", "puzzling"]
        }
        
        self.character_patterns = [
            r"about (?:a |an )?(.+?) who",
            r"protagonist (?:is |named |called )?(.+?)[\.,\s]",
            r"main character (?:is |named |called )?(.+?)[\.,\s]",
            r"story of (?:a |an )?(.+?)[\.,\s]",
        ]
        
        self.setting_patterns = [
            r"set in (.+?)[\.,\s]",
            r"takes place in (.+?)[\.,\s]",
            r"located in (.+?)[\.,\s]",
            r"world of (.+?)[\.,\s]",
        ]
    
    def analyze_prompt(self, prompt: str) -> StoryConfig:
        """Analyze user prompt and extract story parameters"""
        config = StoryConfig()
        config.original_prompt = prompt
        prompt_lower = prompt.lower()
        
        # Extract genre
        genre_scores = {}
        for genre, keywords in self.genre_keywords.items():
            score = sum(1 for keyword in keywords if keyword in prompt_lower)
            if score > 0:
                genre_scores[genre] = score
        
        if genre_scores:
            config.genre = max(genre_scores, key=genre_scores.get)
        
        # Extract length
        for length, keywords in self.length_keywords.items():
            if any(keyword in prompt_lower for keyword in keywords):
                config.length = length
                break
        
        # Extract tone
        for tone, keywords in self.tone_keywords.items():
            if any(keyword in prompt_lower for keyword in keywords):
                config.tone = tone
                break
        
        # Extract protagonist
        for pattern in self.character_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                config.protagonist = match.group(1).strip()
                break
        
        # Extract setting
        for pattern in self.setting_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                config.setting = match.group(1).strip()
                break
        
        return config


class StoryCraftGenerator:
    """Main class for AI Story Generation"""
    
    def __init__(self, api_key: str, model: str = "sarvamai/sarvam-m:free"):
        """Initialize the story generator"""
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        self.console = Console()
        self.stories_dir = Path("generated_stories")
        self.stories_dir.mkdir(exist_ok=True)
        self.analyzer = PromptAnalyzer()
        
        # Setup logging
        self._setup_logging()
        
        self.lengths = {
            "short": {"words": 500, "description": "Short story (~500 words)"},
            "medium": {"words": 1500, "description": "Medium story (~1500 words)"},
            "long": {"words": 3000, "description": "Long story (~3000 words)"},
            "epic": {"words": 5000, "description": "Epic story (~5000 words)"}
        }
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv("LOG_LEVEL", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('storycraft.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _make_api_request(self, prompt: str, max_tokens: int = 4000) -> Optional[str]:
        """Make request to OpenRouter API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/your-repo/storycraft",
            "X-Title": "StoryCraft AI Story Generator",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a masterful storyteller who creates engaging, well-structured stories. Write complete stories with compelling characters, vivid descriptions, and satisfying plot development."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.8,
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True
            ) as progress:
                task = progress.add_task("✨ Crafting your story...", total=None)
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=120
                )
                
                response.raise_for_status()
                result = response.json()
                
                return result['choices'][0]['message']['content']
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            self.console.print(f"[red]❌ Error: API request failed - {e}[/red]")
            return None
        except KeyError as e:
            self.logger.error(f"Unexpected API response format: {e}")
            self.console.print(f"[red]❌ Error: Unexpected response format[/red]")
            return None
    
    def _build_story_prompt(self, user_prompt: str, config: StoryConfig) -> str:
        """Build the story generation prompt"""
        
        # Start with the user's original request
        prompt = f"Write a story based on this request: '{user_prompt}'\n\n"
        
        # Add extracted parameters for guidance
        if config.genre != "general":
            prompt += f"Genre: {config.genre}\n"
        
        if config.length:
            length_info = self.lengths[config.length]
            prompt += f"Length: {length_info['description']}\n"
        
        if config.tone != "neutral":
            prompt += f"Tone: {config.tone}\n"
        
        if config.protagonist:
            prompt += f"Main character: {config.protagonist}\n"
        
        if config.setting:
            prompt += f"Setting: {config.setting}\n"
        
        prompt += f"""
Please create a complete, engaging story that fulfills this request. Make sure to:
- Create compelling characters with clear motivations
- Include vivid descriptions and engaging dialogue
- Ensure the story has a clear beginning, middle, and satisfying end
- Write approximately {self.lengths[config.length]['words']} words

Write the story now:"""
        
        return prompt
    
    def ask_clarifying_questions(self, config: StoryConfig) -> StoryConfig:
        """Ask targeted questions only when needed"""
        
        # Only ask about length if it's not clear from the prompt
        if config.length == "medium" and not any(keyword in config.original_prompt.lower() 
                                                for keywords in self.analyzer.length_keywords.values() 
                                                for keyword in keywords):
            
            self.console.print("\n[dim]📝 How long would you like your story to be?[/dim]")
            self.console.print("[dim]1. Short (~500 words) - Quick read[/dim]")
            self.console.print("[dim]2. Medium (~1500 words) - Standard story[/dim]")
            self.console.print("[dim]3. Long (~3000 words) - Detailed tale[/dim]")
            self.console.print("[dim]4. Epic (~5000 words) - Full adventure[/dim]")
            
            length_choice = Prompt.ask("Choose length", choices=["1", "2", "3", "4"], default="2")
            length_map = {"1": "short", "2": "medium", "3": "long", "4": "epic"}
            config.length = length_map[length_choice]
        
        # Only ask about missing key elements if the story seems incomplete
        if not config.protagonist and not config.setting and config.genre == "general":
            if Confirm.ask("\n[dim]💭 Would you like to add more details about characters or setting?[/dim]", default=False):
                if not config.protagonist:
                    protagonist = Prompt.ask("Main character (optional)", default="")
                    if protagonist:
                        config.protagonist = protagonist
                
                if not config.setting:
                    setting = Prompt.ask("Setting/location (optional)", default="")
                    if setting:
                        config.setting = setting
        
        return config
    
    def display_story_preview(self, config: StoryConfig):
        """Show what we understood from the user's prompt"""
        preview_items = []
        
        if config.genre != "general":
            preview_items.append(f"Genre: {config.genre.title()}")
        
        if config.length:
            preview_items.append(f"Length: {self.lengths[config.length]['description']}")
        
        if config.tone != "neutral":
            preview_items.append(f"Tone: {config.tone.title()}")
        
        if config.protagonist:
            preview_items.append(f"Main character: {config.protagonist}")
        
        if config.setting:
            preview_items.append(f"Setting: {config.setting}")
        
        if preview_items:
            self.console.print(f"\n[dim]📋 Story plan: {' • '.join(preview_items)}[/dim]")
    
    def generate_story(self, user_prompt: str, config: StoryConfig) -> Optional[str]:
        """Generate a story based on user prompt and configuration"""
        prompt = self._build_story_prompt(user_prompt, config)
        max_tokens = min(self.lengths[config.length]["words"] * 2, 4000)
        
        story = self._make_api_request(prompt, max_tokens)
        
        if story:
            self.logger.info(f"Story generated successfully from prompt: {user_prompt[:50]}...")
        
        return story
    
    def save_story(self, story: str, config: StoryConfig) -> Path:
        """Save generated story to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create a safe filename from the prompt
        safe_prompt = re.sub(r'[^\w\s-]', '', config.original_prompt[:30]).strip()
        safe_prompt = re.sub(r'[-\s]+', '_', safe_prompt)
        filename = f"story_{safe_prompt}_{timestamp}.md"
        filepath = self.stories_dir / filename
        
        # Create story metadata
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "original_prompt": config.original_prompt,
            "genre": config.genre,
            "length": config.length,
            "tone": config.tone,
            "protagonist": config.protagonist,
            "setting": config.setting,
            "model": self.model
        }
        
        content = f"""# {config.original_prompt[:50]}{'...' if len(config.original_prompt) > 50 else ''}

## Story Details
- **Original Request**: {config.original_prompt}
- **Genre**: {config.genre.title()}
- **Length**: {self.lengths[config.length]['description']}
- **Generated**: {datetime.now().strftime('%Y-%m-%d at %H:%M')}

---

{story}

---
*Generated by StoryCraft AI Story Generator*
"""
        
        filepath.write_text(content, encoding="utf-8")
        self.logger.info(f"Story saved to {filepath}")
        
        return filepath
    
    def view_story_library(self):
        """Display saved stories"""
        stories = list(self.stories_dir.glob("*.md"))
        
        if not stories:
            self.console.print("[yellow]📚 No stories found in your library yet.[/yellow]")
            return
        
        self.console.print(f"\n[bold cyan]📚 Your Story Library ({len(stories)} stories)[/bold cyan]")
        
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("No.", width=4)
        table.add_column("Story", width=40)
        table.add_column("Created", width=16)
        table.add_column("Size", width=8)
        
        for i, story_path in enumerate(sorted(stories, key=lambda x: x.stat().st_mtime, reverse=True), 1):
            # Extract title from filename
            title = story_path.stem.replace("story_", "").replace("_", " ")
            created = datetime.fromtimestamp(story_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size = f"{story_path.stat().st_size // 1024}KB"
            table.add_row(str(i), title[:35] + "..." if len(title) > 35 else title, created, size)
        
        self.console.print(table)
        
        if Confirm.ask("\n📖 Would you like to read one of these stories?", default=False):
            choice = Prompt.ask("Enter story number", choices=[str(i) for i in range(1, len(stories) + 1)])
            story_path = sorted(stories, key=lambda x: x.stat().st_mtime, reverse=True)[int(choice) - 1]
            
            content = story_path.read_text(encoding="utf-8")
            self.console.print(Panel(Markdown(content), title=f"[bold]📖 {story_path.stem}[/bold]", border_style="blue"))
    
    def run_interactive_mode(self):
        """Run the simplified interactive mode"""
        self.console.print(Panel.fit(
            "[bold green]✨ Welcome to StoryCraft![/bold green]\n"
            "[dim]Just tell me what story you want, and I'll create it for you![/dim]",
            border_style="green"
        ))
        
        while True:
            try:
                # Main menu
                self.console.print("\n" + "="*50)
                self.console.print("[bold]What would you like to do?[/bold]")
                self.console.print("1. 📝 Generate a new story")
                self.console.print("2. 📚 View story library")
                self.console.print("3. 🚪 Exit")
                
                choice = Prompt.ask("Choose option", choices=["1", "2", "3"], default="1")
                
                if choice == "1":
                    # Generate new story
                    self.console.print("\n[bold cyan]📝 Story Generator[/bold cyan]")
                    self.console.print("[dim]Describe the story you want - be as detailed or as simple as you like![/dim]")
                    self.console.print("[dim]Examples:[/dim]")
                    self.console.print("[dim]  • 'A fantasy adventure about a young wizard'[/dim]")
                    self.console.print("[dim]  • 'Write a short horror story set in an abandoned hospital'[/dim]")
                    self.console.print("[dim]  • 'A romantic comedy about two people who meet in a coffee shop'[/dim]")
                    
                    user_prompt = Prompt.ask("\n💭 What's your story idea?")
                    
                    if not user_prompt.strip():
                        self.console.print("[yellow]Please describe your story idea![/yellow]")
                        continue
                    
                    # Analyze the prompt
                    config = self.analyzer.analyze_prompt(user_prompt)
                    
                    # Show what we understood
                    self.display_story_preview(config)
                    
                    # Ask clarifying questions if needed
                    config = self.ask_clarifying_questions(config)
                    
                    # Generate the story
                    story = self.generate_story(user_prompt, config)
                    
                    if story:
                        self.console.print(Panel(
                            Markdown(story),
                            title=f"[bold green]✨ Your Story[/bold green]",
                            border_style="green"
                        ))
                        
                        if Confirm.ask("\n💾 Save this story?", default=True):
                            filepath = self.save_story(story, config)
                            self.console.print(f"[green]✅ Story saved to: {filepath.name}[/green]")
                    else:
                        self.console.print("[red]❌ Failed to generate story. Please try again.[/red]")
                
                elif choice == "2":
                    # View story library
                    self.view_story_library()
                
                elif choice == "3":
                    # Exit
                    self.console.print("[bold green]✨ Happy writing! Come back anytime![/bold green]")
                    break
                
                if choice != "3":
                    input("\nPress Enter to continue...")
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]👋 Goodbye![/yellow]")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                self.console.print(f"[red]❌ An error occurred: {e}[/red]")
    
    def run_single_prompt(self, prompt: str):
        """Generate a single story from command line prompt"""
        config = self.analyzer.analyze_prompt(prompt)
        
        self.console.print(f"[bold cyan]Generating story for:[/bold cyan] {prompt}")
        self.display_story_preview(config)
        
        story = self.generate_story(prompt, config)
        
        if story:
            self.console.print(Panel(
                Markdown(story),
                title="[bold green]✨ Your Story[/bold green]",
                border_style="green"
            ))
            
            if Confirm.ask("\n💾 Save this story?", default=True):
                filepath = self.save_story(story, config)
                self.console.print(f"[green]✅ Story saved to: {filepath.name}[/green]")
        else:
            self.console.print("[red]❌ Failed to generate story.[/red]")


def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    
    # Check if .env file exists, if not create a template
    env_path = Path(".env")
    if not env_path.exists():
        console = Console()
        console.print("[yellow]📁 No .env file found. Creating template...[/yellow]")
        
        env_template = """# StoryCraft Configuration
# Add your OpenRouter API key here
OPENROUTER_API_KEY=your-api-key-here

# Optional: Default model to use
DEFAULT_MODEL=sarvamai/sarvam-m:free

# Optional: Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
"""
        env_path.write_text(env_template)
        console.print(f"[green]✅ Template .env file created at {env_path}[/green]")
        console.print("[bold yellow]📝 Please edit the .env file and add your OpenRouter API key![/bold yellow]")
        return None
    
    return os.getenv("OPENROUTER_API_KEY")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="StoryCraft: AI Story Generator")
    parser.add_argument("--api-key", help="OpenRouter API key (overrides .env)")
    parser.add_argument("--model", help="Model to use (overrides .env)")
    parser.add_argument("--prompt", help="Generate story from this prompt directly")
    
    args = parser.parse_args()
    
    # Load environment variables
    env_api_key = load_environment()
    
    # Get API key from argument, environment, or prompt
    api_key = args.api_key or env_api_key
    
    if not api_key or api_key == "your-api-key-here":
        console = Console()
        if not api_key:
            console.print("[red]❌ No API key found in .env file![/red]")
        else:
            console.print("[red]❌ Please update your .env file with a valid API key![/red]")
        
        console.print("[dim]🔗 You can get an API key from: https://openrouter.ai/[/dim]")
        api_key = Prompt.ask("🔑 Enter your OpenRouter API key", password=True)
    
    if not api_key:
        Console().print("[red]❌ API key is required to run StoryCraft![/red]")
        return
    
    # Get model from argument, environment, or default
    model = args.model or os.getenv("DEFAULT_MODEL", "sarvamai/sarvam-m:free")
    
    # Initialize and run the generator
    try:
        generator = StoryCraftGenerator(api_key, model)
        
        if args.prompt:
            # Direct prompt mode
            generator.run_single_prompt(args.prompt)
        else:
            # Interactive mode
            generator.run_interactive_mode()
            
    except ValueError as e:
        Console().print(f"[red]❌ Error: {e}[/red]")
    except Exception as e:
        console = Console()
        console.print(f"[red]❌ Unexpected error: {e}[/red]")


if __name__ == "__main__":
    main()