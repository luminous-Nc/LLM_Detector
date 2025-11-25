"""YAML configuration loader for game settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


def get_settings_path() -> Path:
    """Get the path to the settings directory."""
    # 从 backend/loaders/ 向上两级到 detective_game，再进入 settings
    current_file = Path(__file__)
    backend_dir = current_file.parent.parent
    detective_game_dir = backend_dir.parent
    settings_dir = detective_game_dir / "settings"
    return settings_dir


def load_yaml_file(filepath: Path) -> Dict[str, Any]:
    """Load a single YAML file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_yaml_directory(directory: Path) -> List[Dict[str, Any]]:
    """Load all YAML files from a directory."""
    results = []
    if not directory.exists():
        return results
    
    for filepath in sorted(directory.glob("*.yaml")):
        data = load_yaml_file(filepath)
        if data:
            results.append(data)
    
    for filepath in sorted(directory.glob("*.yml")):
        data = load_yaml_file(filepath)
        if data:
            results.append(data)
    
    return results


def load_config() -> Dict[str, Any]:
    """Load the main game configuration."""
    settings_path = get_settings_path()
    config_file = settings_path / "config.yaml"
    if config_file.exists():
        return load_yaml_file(config_file)
    return {}


def load_actors() -> Dict[str, Dict[str, Any]]:
    """Load all actor configurations, keyed by actor ID."""
    settings_path = get_settings_path()
    actors_dir = settings_path / "actors"
    
    actors = {}
    for actor_data in load_yaml_directory(actors_dir):
        actor_id = actor_data.get("id")
        if actor_id:
            actors[actor_id] = actor_data
    
    return actors


def load_scenes() -> Dict[str, Dict[str, Any]]:
    """Load all scene configurations, keyed by scene ID."""
    settings_path = get_settings_path()
    scenes_dir = settings_path / "scenes"
    
    scenes = {}
    for scene_data in load_yaml_directory(scenes_dir):
        scene_id = scene_data.get("id")
        if scene_id:
            scenes[scene_id] = scene_data
    
    return scenes


def load_clues() -> Dict[str, Dict[str, Any]]:
    """Load all clue configurations, keyed by clue ID."""
    settings_path = get_settings_path()
    clues_dir = settings_path / "clues"
    
    clues = {}
    for clue_file_data in load_yaml_directory(clues_dir):
        # 每个文件可能包含多个线索（在 clues 列表中）
        clue_list = clue_file_data.get("clues", [])
        for clue_data in clue_list:
            clue_id = clue_data.get("id")
            if clue_id:
                clues[clue_id] = clue_data
    
    return clues


def load_timeline() -> List[Dict[str, Any]]:
    """Load the timeline events."""
    settings_path = get_settings_path()
    timeline_dir = settings_path / "timeline"
    
    events = []
    for timeline_data in load_yaml_directory(timeline_dir):
        event_list = timeline_data.get("events", [])
        events.extend(event_list)
    
    # 按时间排序
    def sort_key(event: Dict[str, Any]) -> tuple:
        trigger = event.get("trigger", {})
        day = trigger.get("day", 0)
        time = trigger.get("time", "dawn")
        time_order = {
            "dawn": 0, "morning": 1, "noon": 2,
            "afternoon": 3, "evening": 4, "night": 5
        }
        return (day, time_order.get(time, 0))
    
    events.sort(key=sort_key)
    return events


def load_all_settings() -> Dict[str, Any]:
    """Load all game settings at once."""
    return {
        "config": load_config(),
        "actors": load_actors(),
        "scenes": load_scenes(),
        "clues": load_clues(),
        "timeline": load_timeline(),
    }


if __name__ == "__main__":
    # 测试加载
    settings = load_all_settings()
    print(f"Loaded config: {settings['config'].get('game', {}).get('title', 'N/A')}")
    print(f"Loaded {len(settings['actors'])} actors")
    print(f"Loaded {len(settings['scenes'])} scenes")
    print(f"Loaded {len(settings['clues'])} clues")
    print(f"Loaded {len(settings['timeline'])} timeline events")

