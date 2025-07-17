import os
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from storycraft import StoryCraftGenerator, PromptAnalyzer, StoryConfig
from pathlib import Path
from dotenv import load_dotenv
import markdown

def clean_story_content(story_text):
    """Clean the story content to remove planning/thinking text.
    
    This function detects and removes the LLM's planning thoughts that sometimes
    appear at the beginning of the generated story.
    """
    # More comprehensive pattern to detect planning sections
    planning_patterns = [
        r"^Check\s+for\s+cultural.*?(?=\n\n|\n[A-Z])",  # "Check for cultural..."
        r"^Ensure\s+the\s+story.*?(?=\n\n|\n[A-Z])",   # "Ensure the story..."
        r"^Avoid\s+any\s+.*?(?=\n\n|\n[A-Z])",         # "Avoid any..."
        r"^Keep\s+paragraphs.*?(?=\n\n|\n[A-Z])",      # "Keep paragraphs..."
        r"^Let\s+me\s+draft.*?(?=\n\n|\n[A-Z])",        # "Let me draft..."
        r"^Maybe\s+.*?(?=\n\n|\n[A-Z])",                # "Maybe..."
        r"^Wait,\s+.*?(?=\n\n|\n[A-Z])",                # "Wait,..."
        r"^Since\s+.*?(?=\n\n|\n[A-Z])",                # "Since..."
        r"^Stick\s+to\s+the\s+request.*?(?=\n\n|\n[A-Z])", # "Stick to the request..."
        r"^Okay,\s+the\s+user\s+wants.*?(?=\n\n|\n[A-Z])",  # "Okay, the user wants..."
        r"^First,\s+I\s+need\s+to.*?(?=\n\n|\n[A-Z])",      # "First, I need to..."
        r"^Let\s+me\s+start\s+by.*?(?=\n\n|\n[A-Z])",       # "Let me start by..."
        r"^I\s+need\s+to\s+build.*?(?=\n\n|\n[A-Z])",       # "I need to build..."
        r"^The\s+main\s+character\s+should\s+be.*?(?=\n\n|\n[A-Z])",  # "The main character should be..."
        r"^Themes:.*?(?=\n\n|\n[A-Z])",                     # "Themes:"
        r"^Plot\s+structure:.*?(?=\n\n|\n[A-Z])",           # "Plot structure:"
        r"^Vivid\s+descriptions:.*?(?=\n\n|\n[A-Z])",       # "Vivid descriptions:"
        r"^Dialogue\s+examples:.*?(?=\n\n|\n[A-Z])",        # "Dialogue examples:"
        r"^Ending:.*?(?=\n\n|\n[A-Z])",                     # "Ending:"
        r"^Need\s+to\s+ensure.*?(?=\n\n|\n[A-Z])",          # "Need to ensure..."
        r"^Make\s+sure\s+the\s+story.*?(?=\n\n|\n[A-Z])",   # "Make sure the story..."
    ]
    
    # Remove planning patterns from the beginning
    cleaned_text = story_text
    for pattern in planning_patterns:
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.DOTALL | re.MULTILINE)
    
    # Remove any remaining planning text at the start
    lines = cleaned_text.split('\n')
    story_start_idx = 0
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if line_lower and not any(keyword in line_lower for keyword in [
            "check for", "ensure", "avoid", "keep", "let me", "maybe", "wait", "since", 
            "stick to", "okay", "first", "i need", "the main", "themes:", "plot", 
            "vivid", "dialogue", "ending:", "need to", "make sure", "step by step",
            "making sure", "draft it"
        ]):
            story_start_idx = i
            break
    
    # Join lines starting from the actual story
    cleaned_lines = lines[story_start_idx:]
    cleaned_text = '\n'.join(cleaned_lines).strip()
    
    # If the text is still empty or too short, return original
    if len(cleaned_text) < 100:
        return story_text.strip()
    
    return cleaned_text

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found in .env file")

generator = StoryCraftGenerator(api_key)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    user_prompt = request.form['prompt']
    
    # Handle file upload
    if 'story_file' in request.files:
        file = request.files['story_file']
        if file.filename != '' and file.filename.endswith('.txt'):
            try:
                file_content = file.read().decode('utf-8')
                if file_content.strip():
                    user_prompt = file_content.strip()
            except:
                pass  # If file read fails, use the text input
    
    if not user_prompt:
        return "Please provide a story prompt", 400
    
    analyzer = PromptAnalyzer()
    config = analyzer.analyze_prompt(user_prompt)
    
    # Override with manual settings if provided
    if request.form.get('length'):
        config.length = request.form['length']
    if request.form.get('genre'):
        config.genre = request.form['genre']
    
    # Set default length if not detected
    if not config.length:
        config.length = 'medium'
    
    story = generator.generate_story(user_prompt, config)
    if story:
        # Clean the story content to remove planning/thinking text
        cleaned_story = clean_story_content(story)
        # Save the cleaned story
        filepath = generator.save_story(cleaned_story, config)
        return redirect(url_for('view_story', filename=filepath.name))
    else:
        return "Error generating story", 500

@app.route('/library')
def library():
    stories_dir = Path('generated_stories')
    stories = sorted(stories_dir.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)
    story_list = [
        {
            'name': p.stem.replace('_', ' ')[:50],  # Remove story_ prefix and replace underscores with spaces
            'filename': p.name,
            'created': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
            'size': f"{p.stat().st_size // 1024}KB"
        }
        for p in stories
    ]
    return render_template('library.html', stories=story_list)

@app.route('/story/<filename>')
def view_story(filename):
    stories_dir = Path('generated_stories')
    filepath = stories_dir / filename
    if not filepath.exists():
        return "Story not found", 404
    content = filepath.read_text(encoding='utf-8')
    html_content = markdown.markdown(content, extensions=['fenced_code', 'codehilite'])
    return render_template('story.html', content=html_content, title=filename.replace('.md', '').replace('_', ' '))

if __name__ == '__main__':
    app.run(debug=True) 