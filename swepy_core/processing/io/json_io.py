import json


def load_json(path):
    """Return a content object for a JSON file"""
    with open(path, 'r') as file:
        return json.load(file)


def save_json(content, path):
    """save a content object in a JSON file"""
    with open(path, 'w') as file:
        json.dump(content, file)
