def log_message(message):
    """Logs a message to the console."""
    print(f"[LOG] {message}")

def load_json(file_path):
    """Loads a JSON file and returns its content."""
    import json
    with open(file_path, 'r') as f:
        return json.load(f)

def save_json(file_path, data):
    """Saves data to a JSON file."""
    import json
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def validate_email(email):
    """Validates an email address format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_unique_id():
    """Generates a unique identifier."""
    import uuid
    return str(uuid.uuid4())